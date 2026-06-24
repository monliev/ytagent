import os
import json
import time
import random
import structlog
from datetime import datetime
from typing import Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from app.models import (
    Channel,
    Video,
    VideoStatus,
    GCPProject,
    GCPProjectStatus,
    ChannelCredentials,
    SystemLog,
    LogLevel
)
from app.utils.credential_crypto import encrypt_token, decrypt_token

logger = structlog.get_logger()

class UploadServiceSync:
    """Service to handle YouTube video upload pipeline in sync worker context.
    
    Manages OAuth decryption, client building, resumable insert operations,
    exponential retry backoff for transient HTTP errors, and GCP project rotation
    upon quota exhaustion.
    """

    def load_client_info(self, client_secret_path: str) -> tuple[str, str, str]:
        """Read GCP client secret file and extract client keys.
        
        Returns:
            tuple[str, str, str]: client_id, client_secret, token_uri
        """
        if not os.path.exists(client_secret_path):
            raise FileNotFoundError(f"Client secret file not found at: {client_secret_path}")
            
        with open(client_secret_path, "r") as f:
            data = json.load(f)
            
        root_key = "installed" if "installed" in data else "web"
        if root_key not in data:
            raise KeyError("Invalid client secret JSON format. Could not find 'installed' or 'web' root.")
            
        info = data[root_key]
        return info["client_id"], info["client_secret"], info.get("token_uri", "https://oauth2.googleapis.com/token")

    def get_youtube_client(self, db: Session, channel_id: int, project_id: str):
        """Decrypt credentials, perform OAuth refresh if needed, and construct Google API clients.
        
        Returns:
            googleapiclient.discovery.Resource: Built YouTube service client.
        """
        # Fetch channel and project credentials
        stmt = select(ChannelCredentials).where(
            ChannelCredentials.channel_id == channel_id,
            ChannelCredentials.gcp_project_id == project_id,
            ChannelCredentials.is_active == True
        )
        creds_rec = db.execute(stmt).scalar_one_or_none()
        if not creds_rec:
            raise ValueError(f"Active credentials not found for channel {channel_id} and project {project_id}")
            
        stmt_proj = select(GCPProject).where(GCPProject.project_id == project_id)
        project_rec = db.execute(stmt_proj).scalar_one_or_none()
        if not project_rec:
            raise ValueError(f"GCP Project details not found for project_id {project_id}")

        if project_rec.client_secret_json:
            decrypted = decrypt_token(channel_id, project_rec.client_secret_json)
            data = json.loads(decrypted)
            root_key = "installed" if "installed" in data else "web"
            if root_key not in data:
                raise KeyError("Invalid client secret JSON format. Could not find 'installed' or 'web' root.")
            info = data[root_key]
            client_id, client_secret, token_uri = info["client_id"], info["client_secret"], info.get("token_uri", "https://oauth2.googleapis.com/token")
        else:
            client_id, client_secret, token_uri = self.load_client_info(project_rec.client_secret_path)
        
        # Decrypt tokens
        refresh_token = decrypt_token(channel_id, creds_rec.oauth_refresh_token_encrypted)
        
        access_token = None
        if creds_rec.oauth_credentials_encrypted:
            try:
                decrypted = decrypt_token(channel_id, creds_rec.oauth_credentials_encrypted)
                if decrypted.startswith("{"):
                    access_token = json.loads(decrypted).get("access_token")
                else:
                    access_token = decrypted
            except Exception as e:
                logger.warning("token_decrypt_failed", error=str(e))

        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret
        )

        # Refresh OAuth token if expired
        try:
            if not creds.valid or (creds.expiry and creds.expiry < datetime.utcnow()):
                logger.info("refreshing_oauth_token", channel_id=channel_id, project_id=project_id)
                creds.refresh(Request())
                
                # Encrypt and save new access token
                creds_rec.oauth_credentials_encrypted = encrypt_token(channel_id, creds.token)
                creds_rec.oauth_token_expiry = creds.expiry
                creds_rec.last_refreshed_at = datetime.utcnow()
                db.add(creds_rec)
                db.commit()
        except Exception as e:
            creds_rec.last_error = f"OAuth refresh failed: {str(e)}"
            db.add(creds_rec)
            db.commit()
            raise RuntimeError(f"Failed to refresh credentials for channel {channel_id}: {e}") from e

        # Build service
        youtube = build("youtube", "v3", credentials=creds)
        return youtube

    def rotate_gcp_project(self, db: Session, channel_id: int, current_project_id: str) -> Optional[GCPProject]:
        """Rotate to the next active GCP project when quota error occurs.
        
        Marks current project status as QUOTA_EXCEEDED.
        """
        logger.warning("quota_exceeded_rotation_triggered", channel_id=channel_id, current_project_id=current_project_id)
        
        # 1. Update current project status to QUOTA_EXCEEDED
        stmt_curr = select(GCPProject).where(GCPProject.project_id == current_project_id)
        curr_proj = db.execute(stmt_curr).scalar_one_or_none()
        if curr_proj:
            curr_proj.status = GCPProjectStatus.QUOTA_EXCEEDED
            db.add(curr_proj)
            db.commit()
            
        # 2. Find next active project for channel
        stmt_next = select(GCPProject).where(
            GCPProject.channel_id == channel_id,
            GCPProject.status == GCPProjectStatus.ACTIVE
        ).order_by(GCPProject.id.asc())
        
        next_proj = db.execute(stmt_next).scalars().first()
        
        # 3. Update Channel's active GCP project ID reference
        if next_proj:
            stmt_chan = select(Channel).where(Channel.id == channel_id)
            channel = db.execute(stmt_chan).scalar_one_or_none()
            if channel:
                channel.gcp_project_id = next_proj.project_id
                db.add(channel)
                db.commit()
            logger.info("rotated_to_new_project", channel_id=channel_id, new_project_id=next_proj.project_id)
            return next_proj
            
        logger.critical("all_gcp_projects_exhausted_for_channel", channel_id=channel_id)
        return None

    def execute_upload(self, db: Session, video: Video) -> str:
        """Execute video upload to YouTube with resumable support and quota checks.
        
        Returns:
            str: YouTube Video ID.
        """
        stmt_chan = select(Channel).where(Channel.id == video.channel_id)
        channel = db.execute(stmt_chan).scalar_one()

        # Retrieve active project ID or select the first available
        active_project_id = channel.gcp_project_id
        if not active_project_id:
            stmt_proj = select(GCPProject).where(
                GCPProject.channel_id == channel.id,
                GCPProject.status == GCPProjectStatus.ACTIVE
            ).order_by(GCPProject.id.asc())
            proj = db.execute(stmt_proj).scalars().first()
            if not proj:
                raise ValueError(f"No active GCP projects configured for channel {channel.name}")
            active_project_id = proj.project_id
            channel.gcp_project_id = active_project_id
            db.add(channel)
            db.commit()

        # Retry loop for quota rotation
        while True:
            try:
                youtube = self.get_youtube_client(db, channel.id, active_project_id)
                youtube_id = self._upload_resumable(youtube, video, channel)
                
                # If playlist_id is configured, insert the video into the playlist
                if video.playlist_id:
                    self._add_video_to_playlist(youtube, youtube_id, video.playlist_id)
                    
                return youtube_id
            except HttpError as e:
                if self._is_quota_error(e):
                    # Rotate GCP Project
                    next_proj = self.rotate_gcp_project(db, channel.id, active_project_id)
                    if next_proj:
                        active_project_id = next_proj.project_id
                        # Retry loop continues with new active project
                        self._log_event_sync(
                            db=db,
                            level=LogLevel.WARNING,
                            service="upload",
                            event_type="quota_rotated",
                            message=f"GCP Project quota limit hit. Rotated to project '{active_project_id}'",
                            video_id=video.id,
                            channel_id=channel.id
                        )
                        continue
                    else:
                        raise RuntimeError(f"All GCP projects for channel '{channel.name}' are exhausted today.") from e
                else:
                    raise
            except Exception as e:
                logger.error("upload_unknown_error", video_id=video.id, error=str(e))
                raise

    def _add_video_to_playlist(self, youtube, video_id: str, playlist_id: str):
        """Add uploaded video to a specific YouTube playlist."""
        try:
            logger.info("adding_video_to_playlist", video_id=video_id, playlist_id=playlist_id)
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id
                        }
                    }
                }
            ).execute()
            logger.info("added_video_to_playlist_success", video_id=video_id, playlist_id=playlist_id)
        except Exception as e:
            logger.error("failed_to_add_video_to_playlist", video_id=video_id, playlist_id=playlist_id, error=str(e))

    def _upload_resumable(self, youtube, video: Video, channel: Channel) -> str:
        """Call standard YouTube resumable insert API and upload chunks."""
        body = {
            "snippet": {
                "title": video.current_title or video.filename,
                "description": video.current_description or "",
                "tags": video.current_tags or [],
                "categoryId": video.category_id or "10"
            },
            "status": {
                "privacyStatus": video.youtube_privacy.value,
                "selfDeclaredMadeForKids": video.made_for_kids
            }
        }

        # Add defaultLanguage and defaultAudioLanguage if configured
        if video.default_language:
            body["snippet"]["defaultLanguage"] = video.default_language
            body["snippet"]["defaultAudioLanguage"] = video.default_language

        # Resumable upload chunk size: 5MB
        media = MediaFileUpload(
            video.file_path,
            mimetype="video/*",
            chunksize=5 * 1024 * 1024,
            resumable=True
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        retry_count = 0
        max_retries = 5

        logger.info("resumable_upload_started", file=video.filename, size=video.file_size_bytes)
        
        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logger.info("upload_chunk_success", video_id=video.id, progress=progress)
                retry_count = 0  # reset on chunk success
            except (HttpError, IOError, Exception) as e:
                # Handle transient error types
                if isinstance(e, HttpError) and self._is_quota_error(e):
                    # Do not retry locally, raise so GCP project rotation can handle it
                    raise
                    
                retry_count += 1
                if retry_count > max_retries:
                    logger.error("resumable_upload_failed_max_retries", video_id=video.id)
                    raise
                    
                sleep_time = (2 ** retry_count) + random.random()
                logger.warning(
                    "resumable_upload_transient_error", 
                    video_id=video.id, 
                    retry=retry_count, 
                    sleep_time=sleep_time, 
                    error=str(e)
                )
                time.sleep(sleep_time)

        youtube_video_id = response.get("id")
        if not youtube_video_id:
            raise RuntimeError("YouTube API response did not contain uploaded video ID.")
            
        return youtube_video_id

    def _is_quota_error(self, e: HttpError) -> bool:
        """Parse HttpError response content to identify if error reason represents quota exhaustion."""
        try:
            content = json.loads(e.content.decode("utf-8"))
            errors = content.get("error", {}).get("errors", [])
            for err in errors:
                reason = err.get("reason", "")
                if reason in ("quotaExceeded", "dailyLimitExceeded", "userRateLimitExceeded"):
                    return True
        except Exception:
            pass
            
        if e.resp.status == 403 or "quota" in str(e).lower():
            return True
        return False

    def _log_event_sync(
        self,
        db: Session,
        level: LogLevel,
        service: str,
        event_type: str,
        message: str,
        video_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        details: Optional[dict[str, Any]] = None
    ) -> None:
        """Insert system log entries synchronously inside session."""
        try:
            log_entry = SystemLog(
                level=level,
                service=service,
                event_type=event_type,
                message=message,
                video_id=video_id,
                channel_id=channel_id,
                details=details
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            logger.error("sync_database_log_insert_failed", error=str(e))
            db.rollback()
