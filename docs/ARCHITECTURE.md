# ARCHITECTURE.md

## YTAgent — System Architecture

> **Version:** 1.0.0
> **Date:** 2025-06-26
> **Status:** Approved
> **Context:** Proxmox home lab, 2 VMs (OMV 4TB + Ubuntu Server 24.04 LTS)

---

## 1. Architecture Overview

YTAgent follows a **modular service-oriented architecture** with clear separation of concerns. The system is designed to run entirely on a single Ubuntu VM using Docker Compose, with file storage on the OMV VM.

### 1.1 Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Single Responsibility** | Each service handles one domain (ingestion, upload, analytics, etc.) |
| **Event-Driven** | File detection triggers cascading events through the pipeline |
| **Sequential Execution** | Upload queue guarantees single-file-at-a-time across all channels |
| **Human-in-the-Loop** | AI prepares drafts; human approves via Telegram |
| **Self-Healing** | Automatic retry for transient failures; safety stops for critical issues |
| **Zero Data Loss** | Original video files are never deleted; all drafts are versioned |

### 1.2 System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SYSTEMS                                │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐  ┌──────────────┐  │
│  │  YouTube    │  │  Telegram    │  │  Cloudflare     │  │  Google      │  │
│  │  Data API   │  │  Bot API     │  │  Workers AI     │  │  Analytics   │  │
│  │  v3         │  │              │  │  (Thumbnail)    │  │  API         │  │
│  └──────┬──────┘  └──────┬───────┘  └────────┬────────┘  └──────┬───────┘  │
│         │                │                   │                  │         │
└─────────┼────────────────┼───────────────────┼──────────────────┼─────────┘
          │                │                   │                  │
          ▼                ▼                   ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           YTAgent (Ubuntu VM)                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        Docker Compose Network                         │   │
│  │                                                                       │   │
│  │   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐    │   │
│  │   │  API     │   │  Worker  │   │ Scheduler│   │ File Watcher │    │   │
│  │   │ (FastAPI)│   │ (Celery) │   │(Celery  │   │ (watchdog)   │    │   │
│  │   │ :8000    │   │          │   │  Beat)   │   │              │    │   │
│  │   └────┬─────┘   └────┬─────┘   └────┬─────┘   └──────┬───────┘    │   │
│  │        │              │              │                │            │   │
│  │        └──────────────┼──────────────┘                │            │   │
│  │                       │                               │            │   │
│  │                       ▼                               ▼            │   │
│  │   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐    │   │
│  │   │  MySQL   │   │  Redis   │   │  Qdrant  │   │ Dashboard    │    │   │
│  │   │  :3306   │   │  :6379   │   │  :6333   │   │ (React/nginx)│    │   │
│  │   │          │   │          │   │          │   │  :80/443     │    │   │
│  │   └──────────┘   └──────────┘   └──────────┘   └──────────────┘    │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    │ SMB/CIFS                                │
│                                    ▼                                         │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │  OMV VM (192.168.1.10)                                               │   │
│   │  /shared/videos/channel_a/                                           │   │
│   │  /shared/videos/channel_a/thumbnails/                                │   │
│   │  /shared/videos/channel_b/                                           │   │
│   │  /shared/videos/channel_b/thumbnails/                                │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Data Flow Architecture

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  DETECT  │───►│ PREPARE  │───►│  NOTIFY  │───►│ EXECUTE  │───►│ ANALYZE  │
│          │    │          │    │          │    │          │    │          │
│ watchdog │    │ ffmpeg   │    │ Telegram │    │ Celery   │    │ YouTube  │
│ ffprobe  │    │ AI Gen   │    │ Bot      │    │ YouTube  │    │ Analytics│
│          │    │          │    │          │    │ API      │    │ Qdrant   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
     ▼               ▼               ▼               ▼               ▼
  MySQL:         MySQL:          MySQL:          MySQL:          MySQL:
  video.status   video.status    video.status    video.status    analytics
  = detected     = staging       = approved      = uploaded      + Qdrant
```

---

## 2. Component Deep-Dive

### 2.1 File Watcher Service (`filewatcher`)

**Purpose:** Monitor OMV shared folders for new video files.

**Technology:** Python `watchdog` with `PollingObserver`

**Deployment:** Standalone Docker container (always running)

**Architecture:**

```python
# Simplified architecture
class OMVFileWatcher:
    """
    Monitors /mnt/omv/[channel_name]/ for new video files.
    Uses polling observer for SMB/CIFS compatibility.
    """
    
    def __init__(self, watch_paths: list[str]):
        self.observer = PollingObserver(timeout=10)
        self.handler = VideoFileHandler()
    
    def start(self):
        for path in watch_paths:
            self.observer.schedule(self.handler, path, recursive=False)
        self.observer.start()
    
    def on_file_created(self, event):
        # 1. Wait for file to be fully copied (size stable for 5 seconds)
        # 2. Validate file type (.mp4, .mov, .avi)
        # 3. Extract metadata via ffprobe (duration, resolution)
        # 4. Map to channel based on parent folder
        # 5. Create database record (status: detected)
        # 6. Trigger Preparation Pipeline (via API call)
        # 7. Send notification: "New video detected"
```

**File Completion Detection:**

```
File Event ──► Wait 5s ──► Check Size ──► Same? ──► YES ──► Process
                │           (stable)                 │
                │                                    ▼
                │                                   NO
                │                                    │
                └────────────────────────────────────┘ (loop)
```

**Configuration:**

```yaml
# docker-compose.yml
filewatcher:
  build: ./services/filewatcher
  volumes:
    - /mnt/omv:/mnt/omv:ro  # Read-only mount
  environment:
    - API_URL=http://api:8000
    - SCAN_INTERVAL=120  # seconds (fallback polling)
    - STABLE_TIMEOUT=5   # seconds (file completion check)
  restart: unless-stopped
```

---

### 2.2 API Service (`api`)

**Purpose:** Central API gateway for all operations. Serves REST endpoints for the dashboard and internal services.

**Technology:** FastAPI + uvicorn

**Deployment:** Docker container with uvicorn ASGI server

**Layer Architecture:**

```
┌─────────────────────────────────────────┐
│           API Service (FastAPI)          │
├─────────────────────────────────────────┤
│  Routes Layer  │  /videos, /channels,    │
│  (Routers)     │  /queue, /analytics,    │
│                │  /upload, /auth, etc.   │
├─────────────────────────────────────────┤
│  Schema Layer  │  Pydantic models for    │
│  (Pydantic)    │  request/response       │
│                │  validation             │
├─────────────────────────────────────────┤
│  Service Layer │  Business logic:        │
│  (Services)    │  - VideoService         │
│                │  - ChannelService       │
│                │  - UploadService        │
│                │  - AnalyticsService     │
│                │  - NotificationService  │
│                │  - ThumbnailService     │
│                │  - MetadataService      │
├─────────────────────────────────────────┤
│  Data Layer    │  SQLAlchemy async ORM   │
│  (Models/DB)   │  Qdrant client          │
│                │  Redis client           │
└─────────────────────────────────────────┘
```

**Key Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/videos` | GET | List videos with filters (status, channel, date) |
| `/videos/{id}` | GET | Video detail with drafts, analytics |
| `/videos/{id}/approve` | POST | Approve video for upload |
| `/videos/{id}/discard` | POST | Discard video draft |
| `/channels` | GET | List all channels |
| `/channels/{id}` | GET/PUT | Channel detail and settings |
| `/channels/{id}/presets` | PUT | Update channel presets |
| `/queue` | GET | Current queue status |
| `/queue/{id}/priority` | PUT | Override queue priority |
| `/upload` | POST | Trigger upload (internal use) |
| `/analytics/{channel_id}` | GET | Channel analytics data |
| `/notifications/send` | POST | Send Telegram notification |
| `/health` | GET | Health check |

---

### 2.3 Celery Worker (`worker`)

**Purpose:** Process background tasks — primarily YouTube uploads.

**Technology:** Celery with Redis broker

**Deployment:** Single-worker Docker container (critical for sequential upload guarantee)

**Task Definitions:**

```python
# tasks/upload.py
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=300,  # 5 minutes
    retry_backoff=True,
    retry_backoff_max=3600,   # Max 1 hour between retries
    retry_jitter=True,        # Prevent thundering herd
)
def upload_video_to_youtube(self, video_id: int):
    """
    Upload video to YouTube. Single worker ensures sequential execution.

    IMPORTANT: Uses synchronous SQLAlchemy Session — NOT AsyncSession.
    Celery runs in a prefork process pool. Calling asyncio.run() inside
    a Celery task causes event loop conflicts and is banned. See AGENT_RULES.md
    Section 6.4 and TECH_DECISIONS.md Section 17 for rationale.
    """
    from app.core.config import settings
    engine = create_engine(settings.sync_database_url)  # mysql+pymysql://...
    try:
        with Session(engine) as db:
            # 1. Load video and channel data from database
            # 2. Load OAuth credentials from channel_credentials table
            # 3. Determine active GCP project (auto-rotation if quota exceeded)
            # 4. Upload video file (resumable, sync google-api-client)
            # 5. Upload thumbnail
            # 6. Set metadata (title, description, tags)
            # 7. Update database status to 'uploaded'
            # 8. Schedule analytics collection (24h, 72h)
            pass
    except YouTubeAPIError as exc:
        # Retry on transient API errors
        raise self.retry(exc=exc)
    except Exception as exc:
        # Log and notify on permanent failure
        logger.error("upload_failed", video_id=video_id, error=str(exc))
        notify_supervisor_sync(video_id, "upload_failed_permanent")
        raise
    finally:
        engine.dispose()

# tasks/analytics.py
@shared_task
def collect_analytics(video_id: int, check_type: str):
    """Collect analytics at 24h or 72h mark."""
    pass

@shared_task
def send_daily_report():
    """Send accumulative report at 08:00 WIB."""
    pass

@shared_task
def check_copyright_claims():
    """Check for copyright claims on all active videos."""
    pass

# tasks/maintenance.py
@shared_task
def rotate_system_logs():
    """Purge system_logs rows older than 30 days. Runs Sunday 02:00 WIB."""
    pass

@shared_task
def reset_daily_gcp_quota():
    """Reset GCP project quota counters daily at 00:05 UTC."""
    pass
```

**Queue Configuration:**

```python
# celeryconfig.py
celery_app = Celery("ytagent")
celery_app.conf.update(
    broker_url="redis://redis:6379/0",
    result_backend="redis://redis:6379/0",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Jakarta",  # WIB
    enable_utc=True,
    # CRITICAL: Single worker for sequential upload
    worker_concurrency=1,
    task_routes={
        "tasks.upload.upload_video_to_youtube": {"queue": "upload"},
        "tasks.analytics.*": {"queue": "analytics"},
        "tasks.notifications.*": {"queue": "notifications"},
    },
    # Task acknowledgment after completion (prevent loss on crash)
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # IMPORTANT: Celery tasks use sync DB sessions (not asyncio).
    # See AGENT_RULES.md Section 6.4 for the canonical pattern.
)
```

---

### 2.4 Celery Beat Scheduler (`scheduler`)

**Purpose:** Trigger periodic tasks (analytics collection, daily reports, copyright checks).

**Deployment:** Separate Docker container from worker

**Schedule:**

```python
# beat_schedule.py
beat_schedule = {
    "check-analytics-24h": {
        "task": "tasks.analytics.check_pending_24h",
        "schedule": crontab(minute="0"),  # Every hour
    },
    "check-analytics-72h": {
        "task": "tasks.analytics.check_pending_72h",
        "schedule": crontab(minute="30"),  # Every hour (offset)
    },
    "send-daily-report": {
        "task": "tasks.analytics.send_daily_report",
        "schedule": crontab(hour="8", minute="0"),  # 08:00 WIB
    },
    "check-copyright-claims": {
        "task": "tasks.upload.check_copyright_claims",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes
    },
    "sync-omv-files": {
        "task": "tasks.ingestion.periodic_sync",
        "schedule": crontab(minute="*/2"),  # Every 2 minutes
    },
}
```

---

### 2.5 Thumbnail & Metadata Generation Pipeline

**Purpose:** AI-powered generation of thumbnails and metadata based on channel presets.

**Flow:**

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  1. Screenshot  │     │  2. AI Thumbnail │     │  3. AI Metadata  │
│  Extraction     │────►│  Generation      │────►│  Generation      │
│                 │     │                  │     │                  │
│ ffmpeg -ss 00:00│     │ Cloudflare AI    │     │ LLM-based gen    │
│ :30 -frames:v 1 │     │ (img2img)        │     │ (prompt-based)   │
│                 │     │                  │     │                  │
│ Output:         │     │ Input: screenshot│     │ Input: filename  │
│ frame30.jpg     │     │ + style_prompt   │     │ + channel preset │
│                 │     │                  │     │                  │
│                 │     │ Output: 3 images │     │ Output: title,   │
│                 │     │ thumb_1/2/3.jpg  │     │ desc, tags       │
└─────────────────┘     └──────────────────┘     └──────────────────┘
                                                         │
                              ┌──────────────────────────┘
                              ▼
                    ┌──────────────────┐
                    │  4. Draft Store  │
                    │                  │
                    │ MySQL: video     │
                    │ status=staging   │
                    │ thumbnail_drafts │
                    │ metadata_drafts  │
                    │ confidence_score │
                    └──────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  5. Notify       │
                    │  Supervisor      │
                    │                  │
                    │ Telegram:        │
                    │ [Approve]        │
                    │ [Edit] [Discard] │
                    └──────────────────┘
```

**Thumbnail Generation Service:**

```python
class ThumbnailService:
    """Generates thumbnails using Cloudflare Workers AI."""
    
    async def generate_options(
        self, 
        screenshot_path: str, 
        channel_id: int
    ) -> list[ThumbnailDraft]:
        # 1. Load channel's thumbnail style preset
        style = await self.get_channel_style(channel_id)
        
        # 2. Build prompts for 3 variations
        prompts = self.build_prompt_variations(style)
        
        # 3. Call Cloudflare AI API for each
        thumbnails = []
        for i, prompt in enumerate(prompts):
            image_data = await self.call_ai_api(screenshot_path, prompt)
            thumb = ThumbnailDraft(
                image_path=f"thumbs/thumb_{i+1}.jpg",
                prompt=prompt,
                style=style.name,
                confidence=self.calculate_confidence(image_data)
            )
            thumbnails.append(thumb)
        
        return thumbnails
    
    async def call_ai_api(self, screenshot_path: str, prompt: str) -> bytes:
        async with httpx.AsyncClient() as client:
            with open(screenshot_path, "rb") as f:
                response = await client.post(
                    settings.cf_ai_url,
                    files={"image": f},
                    data={
                        "prompt": prompt,
                        "strength": 0.7,
                        "guidance": 7.5
                    },
                    timeout=60.0
                )
            return response.content
```

**Metadata Generation Service:**

```python
class MetadataService:
    """Generates title, description, and tags using AI."""
    
    async def generate_draft(
        self,
        video_id: int,
        filename: str,
        channel_id: int
    ) -> MetadataDraft:
        # 1. Parse filename for hints
        hints = self.parse_filename(filename)
        
        # 2. Load channel preset
        preset = await self.get_channel_preset(channel_id)
        
        # 3. Build generation prompt
        prompt = self.build_prompt(hints, preset)
        
        # 4. Generate via LLM (Cloudflare or local model)
        raw_metadata = await self.call_llm(prompt)
        
        # 5. Apply constraints (title length, tag count)
        metadata = self.apply_constraints(raw_metadata)
        
        # 6. Calculate confidence score
        confidence = self.score_confidence(metadata, preset)
        
        return MetadataDraft(
            title=metadata.title,
            description=metadata.description,
            tags=metadata.tags,
            confidence_score=confidence
        )
```

---

### 2.6 Telegram Notification Service

**Purpose:** Send minimalist notifications to Supervisor with inline action buttons.

**Architecture:**

```python
class TelegramService:
    """Handles all Telegram bot interactions."""
    
    def __init__(self):
        self.bot = Bot(token=settings.telegram_bot_token)
        self.dp = Dispatcher()
        self._register_handlers()
    
    def _register_handlers(self):
        # Callback query handlers
        self.dp.callback_query.register(
            self.on_approve, 
            F.data.startswith("approve:")
        )
        self.dp.callback_query.register(
            self.on_edit, 
            F.data.startswith("edit:")
        )
        self.dp.callback_query.register(
            self.on_discard, 
            F.data.startswith("discard:")
        )
    
    async def notify_video_ready(self, video: Video) -> None:
        """Send approval notification to Supervisor."""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Approve", 
                    callback_data=f"approve:{video.id}:{video.channel_id}"
                ),
                InlineKeyboardButton(
                    text="✏️ Edit", 
                    callback_data=f"edit:{video.id}:{video.channel_id}"
                ),
                InlineKeyboardButton(
                    text="🗑️ Discard", 
                    callback_data=f"discard:{video.id}:{video.channel_id}"
                ),
            ]
        ])
        
        await self.bot.send_message(
            chat_id=video.supervisor.telegram_chat_id,
            text=(
                f"🎵 <b>{video.channel.name}</b>\n\n"
                f'"{video.metadata_draft.title}" (Draft)\n'
                f"📅 Jadwal: {video.scheduled_time.strftime('%H:%M WIB')}\n"
                f"🎯 Confidence: {video.metadata_draft.confidence_score}%"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    async def on_approve(self, callback: CallbackQuery):
        """Handle [Approve] button click."""
        _, video_id, channel_id = callback.data.split(":")
        
        # 1. Update video status to 'approved'
        # 2. Add to upload queue
        # 3. Send confirmation
        await callback.answer("✅ Video masuk antrean upload")
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ <b>DISETUJUI</b> — Masuk antrean upload",
            parse_mode="HTML"
        )
```

---

### 2.7 Analytics & Qdrant Integration

**Purpose:** Collect performance data, store vectors, detect patterns, generate insights.

**Data Collection Flow:**

```
YouTube Analytics API ──► Python Service ──► MySQL (raw data)
                                                │
                                                ▼
                    ┌──────────────────────────────────────┐
                    │  Qdrant Vector Store                  │
                    │                                       │
                    │  Collection: video_performance          │
                    │                                       │
                    │  Vector: title_embedding (384-dim)     │
                    │  Payload: {                             │
                    │    video_id, channel_id,               │
                    │    ctr, avd_seconds, views_24h,        │
                    │    thumbnail_style, genre,             │
                    │    title_template, publish_date        │
                    │  }                                     │
                    │                                       │
                    │  Similarity Search:                     │
                    │  "Find videos like this that           │
                    │   performed above average"             │
                    └──────────────────────────────────────┘
                                                │
                                                ▼
                                        Insight Generator
                                        (Pattern Recognition)
                                                │
                                                ▼
                                        Telegram Report (08:00 WIB)
```

**Insight Generation:**

```python
class InsightService:
    """Generates actionable insights from analytics data."""
    
    async def analyze_video(self, video_id: int) -> list[Insight]:
        # 1. Load video performance data
        performance = await self.get_performance(video_id)
        
        # 2. Load channel average
        channel_avg = await self.get_channel_average(video.channel_id)
        
        # 3. Compare and generate insights
        insights = []
        
        if performance.ctr < channel_avg.ctr * 0.5:
            insights.append(Insight(
                type="anomaly",
                severity="warning",
                message=(
                    f"CTR video ini {performance.ctr}%, "
                    f"di bawah rata-rata channel ({channel_avg.ctr}%). "
                    f"Thumbnail mungkin kurang kontras. "
                    f"Coba style 'high-contrast' untuk video berikutnya."
                )
            ))
        
        if performance.avd_seconds < channel_avg.avd_seconds * 0.8:
            insights.append(Insight(
                type="anomaly",
                severity="warning",
                message=(
                    f"AVD drop {performance.avd_seconds}s vs "
                    f"rata-rata {channel_avg.avd_seconds}s. "
                    f"Penonton keluar lebih cepat. "
                    f"Periksa kualitas audio di menit pertama."
                )
            ))
        
        # 4. Qdrant similarity search for positive patterns
        similar_hits = await self.qdrant.search(
            collection="video_performance",
            vector=video.title_embedding,
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="channel_id", match=models.MatchValue(value=video.channel_id)
                    ),
                    models.FieldCondition(
                        key="ctr", range=models.Range(gte=channel_avg.ctr)
                    )
                ]
            ),
            limit=5
        )
        
        if similar_hits:
            best = similar_hits[0]
            insights.append(Insight(
                type="suggestion",
                severity="info",
                message=(
                    f"💡 Video dengan judul serupa '{best.payload['title']}' "
                    f"mendapat CTR {best.payload['ctr']}%. "
                    f"Pertimbangkan pola judul tersebut."
                )
            ))
        
        return insights
```

---

### 2.8 Dashboard (React Frontend)

**Purpose:** Web UI for channel management, staging, queue monitoring, and analytics.

**Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│  Dashboard (React 18 + Tailwind + shadcn/ui)                │
├─────────────────────────────────────────────────────────────┤
│  Layout                                                     │
│  ├── Sidebar (Channel Selector + Navigation)                │
│  ├── Header (User, Notifications, Global Actions)           │
│  └── Main Content Area                                      │
├─────────────────────────────────────────────────────────────┤
│  State Management (Zustand)                                 │
│  ├── useChannelStore (selected channel, channel list)       │
│  ├── useVideoStore (videos, drafts, staging)                │
│  ├── useQueueStore (queue status, tasks)                    │
│  └── useAnalyticsStore (metrics, charts, insights)          │
├─────────────────────────────────────────────────────────────┤
│  API Layer (TanStack Query)                                 │
│  ├── useVideos() (caching, refetching)                      │
│  ├── useChannels()                                          │
│  ├── useQueue()                                             │
│  └── useAnalytics()                                         │
├─────────────────────────────────────────────────────────────┤
│  Components (shadcn/ui + custom)                            │
│  ├── DataTable (TanStack Table)                             │
│  ├── Chart (Recharts)                                       │
│  ├── VideoCard (thumbnail preview)                          │
│  ├── MetadataEditor (form)                                  │
│  └── QueueStatus (real-time indicator)                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Data Storage Architecture

### 3.1 MySQL Schema Strategy

**Normalized relational data** for core entities. **JSON columns** for flexible drafts and configurations.

| Table Type | Examples | Storage |
|-----------|----------|---------|
| Core Entities | channels, videos, users | Normalized columns |
| Drafts | metadata_drafts, thumbnail_drafts | JSON columns |
| Configurations | channel_presets | JSON columns |
| Logs | system_logs, api_logs | JSON columns + indexed fields |
| Analytics | analytics_records | Normalized columns (for querying) |

### 3.2 Redis Usage

| Purpose | Key Pattern | TTL |
|---------|------------|-----|
| Celery broker | `celery:*` | N/A |
| Celery results | `celery-task-meta-*` | 1 hour |
| Upload lock | `upload:lock` | 1 hour |
| Rate limiting | `rate_limit:{ip}` | 1 minute |
| Cache: channel list | `cache:channels` | 5 minutes |
| Cache: queue status | `cache:queue` | 30 seconds |
| **Approval idempotency** | `approve:lock:{video_id}` | **5 minutes** |

**Approval Idempotency Lock:**
When `/videos/{id}/approve` is called, set a Redis key `approve:lock:{video_id}` with 5-minute TTL **before** the database transaction. If the key already exists, return `200 {"status": "already_approved"}` immediately — prevents race condition between Telegram and Dashboard dual-approval. See AGENT_RULES.md Section 11 for full flow.

### 3.3 Qdrant Collections

| Collection | Vector Size | Payload Fields | Purpose |
|-----------|-------------|----------------|---------|
| `video_performance` | 384 | video_id, channel_id, ctr, avd, views, style, genre | Pattern recognition |
| `title_embeddings` | 384 | title_text, channel_id, performance_score | Title similarity |
| `thumbnail_styles` | 512 | style_name, channel_id, performance_score | Style comparison |

---

## 4. Communication Patterns

### 4.1 Synchronous (Request/Response)

| Source | Target | Protocol | Use Case |
|--------|--------|----------|----------|
| Dashboard | FastAPI | HTTP/REST | All CRUD operations |
| File Watcher | FastAPI | HTTP/REST | Notify new video detected |
| FastAPI | MySQL | TCP (asyncmy) | Database operations |
| FastAPI | Redis | TCP (redis-py) | Cache, queue state |
| FastAPI | Qdrant | HTTP | Vector search |
| Telegram Bot | FastAPI | HTTP (webhook/polling) | Callback handling |

### 4.2 Asynchronous (Event-Driven)

| Producer | Consumer | Broker | Event |
|----------|----------|--------|-------|
| File Watcher | Celery Worker | Redis (via API) | `video.detected` → trigger preparation |
| FastAPI | Celery Worker | Redis | `video.approved` → trigger upload |
| Celery Beat | Celery Worker | Redis | Scheduled: analytics, reports, checks |
| Upload Task | Celery Beat | Redis | `upload.complete` → schedule analytics |

### 4.3 File System

| Source | Target | Path | Files |
|--------|--------|------|-------|
| Editor | OMV | `/shared/videos/[channel]/` | `.mp4`, `.mov` |
| File Watcher | OMV (thumbnails) | `/shared/videos/[channel]/thumbnails/` | `.jpg` |
| API/Worker | OMV (read) | `/mnt/omv/[channel]/` | Video + thumbnail files |

---

## 5. Security Architecture

### 5.1 Authentication Flow

```
┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
│ Supervisor│─────►│ Dashboard│─────►│ FastAPI  │─────►│  MySQL   │
│          │ Login │ (React)  │ POST  │ (JWT)    │ Verify│ (User)  │
└──────────┘      └──────────┘      └──────────┘      └──────────┘
                                          │
                                          │ JWT Token
                                          ▼
                                    ┌──────────┐
                                    │  Client  │
                                    │  Stores  │
                                    │  Token   │
                                    └──────────┘
```

### 5.2 OAuth Token Management

```
┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
│  MySQL   │─────►│ FastAPI  │─────►│ Google   │─────►│ YouTube  │
│ (Encrypt │ Decrypt│ Service │ Auth  │ OAuth    │ API   │          │
│  Token)  │      │          │       │ Refresh  │       │          │
└──────────┘      └──────────┘      └──────────┘      └──────────┘
```

**Token Encryption:**
- Algorithm: Fernet (symmetric encryption from `cryptography` library)
- Key stored in environment variable (`TOKEN_ENCRYPTION_KEY`)
- Tokens refreshed automatically via Celery task before expiry

### 5.3 Network Security

```
Internet ──► [Firewall] ──► Ubuntu VM
                              │
                              ├──► :80/443  Dashboard (nginx)
                              ├──► :8000    FastAPI (internal network)
                              │
                              Docker Network (isolated)
                              ├──► MySQL :3306 (not exposed)
                              ├──► Redis :6379 (not exposed)
                              ├──► Qdrant :6333 (not exposed)
                              └──► All other services (internal only)
```

---

## 6. Error Handling & Recovery

### 6.1 Failure Scenarios

| Scenario | Detection | Response | Recovery |
|----------|-----------|----------|----------|
| Network failure during upload | API timeout | Retry ×5 with backoff | Auto (no human) |
| YouTube API quota exceeded | HTTP 403 + quota error | Pause queue, alert | Manual (wait 24h or switch GCP) |
| OAuth token expired | HTTP 401 | Auto-refresh token | Auto (no human) |
| File corruption | ffprobe failure | Log error, discard | Manual (re-render) |
| Copyright claim detected | YouTube API claim check | STOP all queues, critical alert | Manual (Supervisor resume) |
| OMV mount disconnected | File watcher error | Pause detection, alert | Manual (check network) |
| Redis/Celery crash | Health check failure | Alert, queue pauses | Auto (Docker restart) |
| MySQL unavailable | Connection error | API returns 503, retry | Auto (Docker restart) |
| Cloudflare AI API down | HTTP error | Use raw screenshot, notify | Auto (fallback) |

### 6.2 Circuit Breaker Pattern

For external APIs (YouTube, Cloudflare, Telegram):

```python
class CircuitBreaker:
    """Prevents cascading failures."""
    
    def __init__(self, failure_threshold=5, recovery_timeout=300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpen("Service temporarily unavailable")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
    
    def _on_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
```

---

## 7. Scalability Considerations

### 7.1 Current Scale

| Metric | Value |
|--------|-------|
| Channels | 10–30 |
| Videos per day | 10–30 (1 per channel) |
| Upload frequency | 1 at a time (sequential) |
| Storage (OMV) | 4TB |
| Concurrent users | 1–2 (Editor + Supervisor) |

### 7.2 Scaling Vectors

| Bottleneck | Current | Future Scale | Mitigation |
|-----------|---------|-------------|------------|
| Upload throughput | 1 video at a time | N/A (by design) | Sequential is intentional |
| GCP quota | 6 uploads/project/day | More channels | Multiple GCP projects + **auto-rotation** |
| MySQL connections | ~10 | More workers | Connection pooling |
| OMV storage | 4TB | Growing | Manual expansion (add HDD) |
| AI thumbnail API | Free tier | Rate limits | Fallback to local PIL overlay |
| VM resources | 4 vCPU / 8GB | More channels | Scale VM resources |

### 7.3 GCP Quota Auto-Rotation

When a channel's GCP project hits quota, the system automatically tries the next available project assigned to that channel instead of stopping the queue.

```
Upload attempt
    │
    ▼
Load GCP project for channel (status='active', quota_used < quota_limit)
    │
    ├─► SUCCESS → Upload proceeds
    │
    └─► QuotaExceededError (HTTP 403)
            │
            ▼
        Mark project status='quota_exceeded' for today
            │
            ▼
        Find next available project for this channel?
            │
           YES → Retry upload with new credentials
            │
            NO  → Alert Supervisor "All GCP projects for {channel} exhausted today"
                  Pause channel queue until next day
```

**Implementation Notes:**
- `gcp_projects.last_reset` is checked daily; quota resets at midnight UTC.
- A Celery Beat task runs daily at 00:05 UTC to reset `quota_used=0` and set `status='active'`.
- Channels can have multiple GCP projects in `gcp_projects` table (one-to-many).

### 7.4 Horizontal Scaling (Future)

If channels grow beyond 50:

```
┌─────────────────────────────────────────┐
│           Load Balancer (nginx)          │
│         (Round-robin to API instances)   │
└─────────────────────────────────────────┘
                   │
      ┌────────────┼────────────┐
      ▼            ▼            ▼
┌─────────┐  ┌─────────┐  ┌─────────┐
│ API #1  │  │ API #2  │  │ API #3  │
│ (stateless)│ (stateless)│ (stateless)│
└────┬────┘  └────┬────┘  └────┬────┘
     └────────────┼────────────┘
                  ▼
         ┌─────────────┐
         │  Shared DB   │
         │  (MySQL)     │
         │  (Redis)     │
         └─────────────┘
```

**Note:** Upload worker remains single-instance to maintain sequential queue guarantee.

---

## 8. Deployment Architecture

### 8.1 Docker Compose Stack

```yaml
# docker-compose.yml (production)
version: "3.8"

services:
  # Core Infrastructure
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ytagent
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    volumes:
      - mysql_data:/var/lib/mysql
      - ./init-scripts:/docker-entrypoint-initdb.d
    ports:
      - "127.0.0.1:3306:3306"  # Local only
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    ports:
      - "127.0.0.1:6379:6379"
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - qdrant_data:/qdrant/storage
    ports:
      - "127.0.0.1:6333:6333"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Application Services
  api:
    build:
      context: ./app
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=mysql+asyncmy://${MYSQL_USER}:${MYSQL_PASSWORD}@mysql:3306/ytagent
      - REDIS_URL=redis://redis:6379/0
      - QDRANT_URL=http://qdrant:6333
    volumes:
      - /mnt/omv:/mnt/omv:ro
      - ./secrets:/secrets:ro
    ports:
      - "8000:8000"
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_healthy
    restart: unless-stopped

  worker:
    build:
      context: ./app
      dockerfile: Dockerfile.worker
    environment:
      - DATABASE_URL=mysql+asyncmy://${MYSQL_USER}:${MYSQL_PASSWORD}@mysql:3306/ytagent
      - REDIS_URL=redis://redis:6379/0
      - QDRANT_URL=http://qdrant:6333
    volumes:
      - /mnt/omv:/mnt/omv:ro
      - ./secrets:/secrets:ro
    depends_on:
      - mysql
      - redis
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 2G

  scheduler:
    build:
      context: ./app
      dockerfile: Dockerfile.worker
    command: celery -A tasks beat -l info
    environment:
      - DATABASE_URL=mysql+asyncmy://${MYSQL_USER}:${MYSQL_PASSWORD}@mysql:3306/ytagent
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
    restart: unless-stopped

  filewatcher:
    build:
      context: ./services/filewatcher
    environment:
      - API_URL=http://api:8000
      - SCAN_INTERVAL=120
    volumes:
      - /mnt/omv:/mnt/omv:ro
    depends_on:
      - api
    restart: unless-stopped

  dashboard:
    build:
      context: ./dashboard
      dockerfile: Dockerfile
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api
    restart: unless-stopped

volumes:
  mysql_data:
  redis_data:
  qdrant_data:
```

### 8.2 Environment Variables

```bash
# .env (production)
# MySQL
MYSQL_ROOT_PASSWORD=<secure_random>
MYSQL_USER=ytagent
MYSQL_PASSWORD=<secure_random>

# Redis
REDIS_URL=redis://redis:6379/0

# FastAPI
SECRET_KEY=<jwt_signing_key>
API_HOST=0.0.0.0
API_PORT=8000

# Telegram
TELEGRAM_BOT_TOKEN=<bot_token_from_botfather>

# Cloudflare AI
CF_AI_URL=https://<worker>.workers.dev/

# Encryption
TOKEN_ENCRYPTION_KEY=<fernet_key_base64>

# OMV
OMV_MOUNT_PATH=/mnt/omv

# Timezone
TZ=Asia/Jakarta
```

---

## 9. Health Check & Monitoring

### 9.1 Health Check Endpoints

| Service | Endpoint | Expected Response |
|---------|----------|-------------------|
| FastAPI | `GET /health` | `{"status": "ok", "version": "1.0.0"}` |
| MySQL | `mysqladmin ping` | `mysqld is alive` |
| Redis | `redis-cli ping` | `PONG` |
| Qdrant | `GET /healthz` | HTTP 200 |
| Celery Worker | Flower dashboard | Active worker count >= 1 |

### 9.2 Monitoring Stack (Lightweight)

Given resource constraints (home lab), use a lightweight monitoring approach:

| Component | Tool | Purpose |
|-----------|------|---------|
| Log Aggregation | Built-in JSON logs + file | Centralized logging |
| Health Dashboard | FastAPI `/health` endpoint | Service status |
| Queue Monitoring | Flower (Celery) | Task queue visualization |
| System Metrics | Built-in Docker stats | CPU, memory usage |
| Alerts | Telegram bot | Critical notifications |

**Note:** Full monitoring stack (Prometheus + Grafana) is out of scope for MVP but can be added later.
