import os
import json
import httpx
import structlog
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.config import settings
from app.models import (
    Channel, GCPProject, ChannelCredentials, Video, VideoStatus,
    AnalyticsRecord, PerformanceInsight
)
from app.models.performance_insight import InsightType, InsightSeverity
from app.utils.credential_crypto import decrypt_token, encrypt_token

logger = structlog.get_logger()

def get_google_credentials(db: Session, channel: Channel) -> Optional[Credentials]:
    """Helper to decrypt and build google.oauth2.credentials.Credentials for a channel."""
    try:
        if not channel.gcp_project_id:
            return None
            
        project_rec = db.query(GCPProject).filter(GCPProject.project_id == channel.gcp_project_id).first()
        if not project_rec:
            return None
            
        creds_rec = db.query(ChannelCredentials).filter(
            ChannelCredentials.channel_id == channel.id,
            ChannelCredentials.gcp_project_id == channel.gcp_project_id,
            ChannelCredentials.is_active == True
        ).first()
        if not creds_rec:
            return None
            
        # Decrypt client secret
        if project_rec.client_secret_json:
            decrypted = decrypt_token(channel.id, project_rec.client_secret_json)
            data = json.loads(decrypted)
            root_key = "installed" if "installed" in data else "web"
            info = data[root_key]
            client_id = info["client_id"]
            client_secret = info["client_secret"]
            token_uri = info.get("token_uri", "https://oauth2.googleapis.com/token")
        else:
            if not os.path.exists(project_rec.client_secret_path):
                return None
            with open(project_rec.client_secret_path, "r") as f:
                data = json.load(f)
            root_key = "installed" if "installed" in data else "web"
            info = data[root_key]
            client_id = info["client_id"]
            client_secret = info["client_secret"]
            token_uri = info.get("token_uri", "https://oauth2.googleapis.com/token")
            
        # Decrypt tokens
        refresh_token = decrypt_token(channel.id, creds_rec.oauth_refresh_token_encrypted)
        access_token = None
        if creds_rec.oauth_credentials_encrypted:
            try:
                decrypted = decrypt_token(channel.id, creds_rec.oauth_credentials_encrypted)
                if decrypted.startswith("{"):
                    access_token = json.loads(decrypted).get("access_token")
                else:
                    access_token = decrypted
            except Exception:
                pass
                
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Refresh token if expired
        if not creds.valid or (creds.expiry and creds.expiry < datetime.utcnow()):
            creds.refresh(Request())
            # Save back encrypted access token
            creds_rec.oauth_credentials_encrypted = encrypt_token(channel.id, creds.token)
            creds_rec.oauth_token_expiry = creds.expiry
            creds_rec.last_refreshed_at = datetime.utcnow()
            db.add(creds_rec)
            db.commit()
            
        return creds
    except Exception as e:
        logger.error("failed_to_get_google_credentials", channel_id=channel.id, error=str(e))
        return None

def generate_performance_insights(db: Session, channel_id: int, video: Video, record: AnalyticsRecord):
    """Analyze the metrics and write performance insights/suggestions. Calls Cloudflare LLM if URL configured, otherwise uses heuristic engine."""
    suggestions = []
    
    # 1. Low CTR check
    if record.views > 20 and record.ctr is not None and record.ctr < Decimal("3.0"):
        suggestions.append({
            "insight_type": InsightType.SUGGESTION,
            "title": "Optimasi Thumbnail & Judul Diperlukan",
            "message": f"Video '{video.current_title or video.filename}' memiliki Rasio Klik-Tayang (CTR) sangat rendah ({record.ctr}%). Penonton melihat video tetapi jarang mengkliknya.",
            "severity": InsightSeverity.WARNING,
            "metric_type": "ctr",
            "metric_value": record.ctr,
            "metric_average": Decimal("5.0"),
            "suggested_action": "Buat ulang desain thumbnail dengan kontras warna yang lebih tinggi atau teks yang lebih pendek dan mencolok. Coba ganti judul video dengan sesuatu yang memicu rasa ingin tahu."
        })
        
    # 2. Clickbait warning (high CTR but low average view duration)
    if record.views > 50 and record.ctr is not None and record.ctr > Decimal("7.0") and record.avd_percentage is not None and record.avd_percentage < Decimal("30.0"):
        suggestions.append({
            "insight_type": InsightType.ANOMALY,
            "title": "Indikasi Klikbait: Retensi Rendah",
            "message": f"CTR video tinggi ({record.ctr}%), tetapi penonton langsung pergi dengan rata-rata retensi tonton hanya {record.avd_percentage}%. Penonton merasa kurang puas dengan pembukaan video.",
            "severity": InsightSeverity.CRITICAL,
            "metric_type": "avd_percentage",
            "metric_value": record.avd_percentage,
            "metric_average": Decimal("50.0"),
            "suggested_action": "Pastikan 15-30 detik pertama video langsung menjawab ekspektasi penonton dari thumbnail/judul. Evaluasi bagian hook pembuka."
        })
        
    # 3. Low engagement CTA suggest
    if record.views > 100 and record.likes > 0 and (record.likes / record.views) < 0.02:
        engagement_rate = round((record.likes / record.views) * 100, 2)
        suggestions.append({
            "insight_type": InsightType.SUGGESTION,
            "title": "Tingkatkan Rasio Suka (Likes)",
            "message": f"Rasio likes terhadap views cukup rendah ({engagement_rate}%). Penonton kurang termotivasi memberikan interaksi suka.",
            "severity": InsightSeverity.INFO,
            "metric_type": "likes_ratio",
            "metric_value": Decimal(str(engagement_rate)),
            "metric_average": Decimal("4.0"),
            "suggested_action": "Sematkan ajakan menyukai video (call to action) di bagian awal video atau tulis komentar terpaku (pinned comment) yang ramah."
        })

    # 4. Low comment count check
    if record.views > 100 and record.comments == 0:
        suggestions.append({
            "insight_type": InsightType.SUGGESTION,
            "title": "Kolom Komentar Masih Sepi",
            "message": f"Video ini sudah ditonton {record.views} kali tetapi belum ada komentar. Keaktifan diskusi kolom komentar dinilai penting oleh algoritma YouTube.",
            "severity": InsightSeverity.INFO,
            "metric_type": "comments",
            "metric_value": Decimal("0.0"),
            "metric_average": Decimal("1.0"),
            "suggested_action": "Tulis pin comment berupa pertanyaan terbuka untuk mengundang diskusi hangat dari penonton."
        })
        
    # 5. Milestone celebration!
    if record.views >= 1000 and record.views_gained is not None and record.views_gained > 10:
        suggestions.append({
            "insight_type": InsightType.MILESTONE,
            "title": "Milestone: 1,000+ Views!",
            "message": f"Selamat! Video '{video.current_title or video.filename}' telah menembus total {record.views} views.",
            "severity": InsightSeverity.INFO,
            "metric_type": "views",
            "metric_value": Decimal(str(record.views)),
            "metric_average": Decimal("1000.0"),
            "suggested_action": "Pertimbangkan untuk membuat konten kelanjutan atau topik serupa karena penonton menunjukkan minat yang besar."
        })

    # Fallback to LLM if settings.CF_AI_URL is active
    if settings.CF_AI_URL and "dummy" not in settings.CF_AI_URL:
        try:
            prompt = f"""
            Analyze YouTube video performance metrics:
            Title: {video.current_title or video.filename}
            Views: {record.views}
            Likes: {record.likes}
            Comments: {record.comments}
            CTR: {record.ctr}%
            Avg View Duration: {record.avd_seconds} seconds
            Total duration: {video.duration_seconds or 'unknown'} seconds

            Provide a short, actionable optimization recommendation for the creator in Indonesian language.
            Be concise. Title should be maximum 8 words, message maximum 30 words, suggested action maximum 20 words.
            Format response strictly as JSON: {{"title": "Title in Indo", "message": "Recommendation message in Indo", "suggested_action": "Action plan in Indo", "severity": "info/warning/critical"}}
            """
            resp = httpx.post(
                settings.CF_AI_URL,
                json={"prompt": prompt, "system_instruction": "You are a professional YouTube SEO and growth strategist."},
                timeout=8.0
            )
            if resp.status_code == 200:
                ai_data = resp.json()
                if "response" in ai_data:
                    text = ai_data["response"]
                    start_idx = text.find("{")
                    end_idx = text.rfind("}")
                    if start_idx != -1 and end_idx != -1:
                        parsed = json.loads(text[start_idx:end_idx+1])
                        suggestions.append({
                            "insight_type": InsightType.SUGGESTION,
                            "title": parsed.get("title", "Rekomendasi Optimasi AI"),
                            "message": parsed.get("message", "Performa video siap dioptimasi."),
                            "severity": parsed.get("severity", "info").lower(),
                            "metric_type": "ai_custom",
                            "metric_value": record.views,
                            "metric_average": record.views,
                            "suggested_action": parsed.get("suggested_action", "Sesuaikan thumbnail dan judul.")
                        })
        except Exception as e:
            logger.warning("cf_ai_text_generation_failed_for_insights", error=str(e))

    # Save suggestions to DB (delete previous unread ones first to avoid spamming)
    db.query(PerformanceInsight).filter(
        PerformanceInsight.video_id == video.id,
        PerformanceInsight.is_read == False
    ).delete()
    
    for s in suggestions:
        insight = PerformanceInsight(
            channel_id=channel_id,
            video_id=video.id,
            insight_type=s["insight_type"],
            title=s["title"],
            message=s["message"],
            severity=InsightSeverity(s["severity"]) if s["severity"] in ["info", "warning", "critical"] else InsightSeverity.INFO,
            metric_type=s["metric_type"],
            metric_value=s["metric_value"],
            metric_average=s["metric_average"],
            suggested_action=s["suggested_action"],
            is_actionable=True,
            is_read=False
        )
        db.add(insight)

@celery_app.task(name="app.tasks.analytics.sync_youtube_analytics")
def sync_youtube_analytics() -> dict:
    """Periodic task that fetches both channel-level and video-level analytics from YouTube."""
    logger.info("celery_sync_youtube_analytics_started")
    synced_channels = []
    
    with SessionLocal() as db:
        channels = db.query(Channel).filter(Channel.is_active == True).all()
        for channel in channels:
            try:
                creds = get_google_credentials(db, channel)
                if not creds:
                    logger.warning("skipping_analytics_sync_no_credentials", channel_id=channel.id)
                    continue
                
                # Fetch statistics from YouTube Data API (real-time views, likes, comments)
                videos = db.query(Video).filter(
                    Video.channel_id == channel.id,
                    Video.youtube_video_id != None,
                    Video.status == VideoStatus.UPLOADED
                ).all()
                
                if not videos:
                    logger.info("no_uploaded_videos_for_analytics", channel_id=channel.id)
                    synced_channels.append({"channel_id": channel.id, "videos_synced": 0})
                    continue
                
                # Build Google APIs clients
                youtube_data = build("youtube", "v3", credentials=creds)
                youtube_analytics = build("youtubeAnalytics", "v2", credentials=creds)
                
                video_ids_map = {v.youtube_video_id: v for v in videos}
                yt_video_ids = list(video_ids_map.keys())
                
                video_stats = {}
                for i in range(0, len(yt_video_ids), 50):
                    batch_ids = yt_video_ids[i:i+50]
                    res = youtube_data.videos().list(
                        id=",".join(batch_ids),
                        part="statistics"
                    ).execute()
                    
                    for item in res.get("items", []):
                        yid = item["id"]
                        stats = item.get("statistics", {})
                        video_stats[yid] = {
                            "views": int(stats.get("viewCount", 0)),
                            "likes": int(stats.get("likeCount", 0)),
                            "dislikes": int(stats.get("dislikeCount", 0)),
                            "comments": int(stats.get("commentCount", 0)),
                            "shares": 0
                        }
                
                # Retrieve report grouped by video over the last 30 days
                end_date = datetime.utcnow().strftime("%Y-%m-%d")
                start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
                
                analytics_data = {}
                try:
                    filters = f"video=={','.join(yt_video_ids[:200])}"
                    report = youtube_analytics.reports().query(
                        ids="channel==MINE",
                        startDate=start_date,
                        endDate=end_date,
                        metrics="views,likes,comments,shares,estimatedMinutesWatched,averageViewDuration,videoThumbnailImpressionsClickRate",
                        dimensions="video",
                        filters=filters
                    ).execute()
                    
                    columns = [h["name"] for h in report.get("columnHeaders", [])]
                    for row in report.get("rows", []):
                        row_dict = dict(zip(columns, row))
                        yid = row_dict.get("video")
                        if yid:
                            # Convert ClickRate decimal safely
                            ctr_val = row_dict.get("videoThumbnailImpressionsClickRate")
                            ctr_dec = Decimal(str(ctr_val)) * 100 if ctr_val is not None else Decimal("4.2")
                            analytics_data[yid] = {
                                "ctr": ctr_dec,
                                "avd_seconds": int(row_dict.get("averageViewDuration") or 0),
                            }
                except Exception as e:
                    logger.warning("youtube_analytics_video_query_failed", channel_id=channel.id, error=str(e))
                
                recorded_at = datetime.utcnow()
                videos_synced_count = 0
                
                for yid, stats in video_stats.items():
                    video_obj = video_ids_map[yid]
                    extra = analytics_data.get(yid, {})
                    ctr = extra.get("ctr", Decimal("4.2"))
                    avd_seconds = extra.get("avd_seconds", 0)
                    
                    avd_percentage = None
                    if video_obj.duration_seconds and video_obj.duration_seconds > 0:
                        avd_percentage = Decimal(str(round((avd_seconds / video_obj.duration_seconds) * 100, 2)))
                    
                    hours_since_publish = 0
                    if video_obj.uploaded_at:
                        hours_since_publish = int((recorded_at - video_obj.uploaded_at).total_seconds() / 3600)
                    
                    prev_rec = db.query(AnalyticsRecord).filter(
                        AnalyticsRecord.video_id == video_obj.id
                    ).order_by(AnalyticsRecord.recorded_at.desc()).first()
                    
                    views_gained = stats["views"]
                    if prev_rec:
                        views_gained = max(0, stats["views"] - prev_rec.views)
                    
                    new_record = AnalyticsRecord(
                        video_id=video_obj.id,
                        channel_id=channel.id,
                        youtube_video_id=yid,
                        recorded_at=recorded_at,
                        hours_since_publish=hours_since_publish,
                        views=stats["views"],
                        views_gained=views_gained,
                        likes=stats["likes"],
                        dislikes=stats["dislikes"],
                        comments=stats["comments"],
                        shares=stats["shares"],
                        ctr=ctr,
                        avd_seconds=avd_seconds,
                        avd_percentage=avd_percentage
                    )
                    db.add(new_record)
                    videos_synced_count += 1
                    
                    # Generate Insights
                    generate_performance_insights(db, channel.id, video_obj, new_record)
                
                db.commit()
                logger.info("analytics_sync_channel_completed", channel_id=channel.id, count=videos_synced_count)
                synced_channels.append({"channel_id": channel.id, "videos_synced": videos_synced_count})
                
            except Exception as ex:
                logger.error("failed_sync_channel_analytics", channel_id=channel.id, error=str(ex))
                db.rollback()
                
    return {"status": "success", "channels": synced_channels}
