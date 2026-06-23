# TECH_DECISIONS.md

## YTAgent — Technology Decision Records

> **Version:** 1.0.0
> **Date:** 2025-06-26
> **Status:** Approved
> **Context:** Proxmox home lab, 2 VMs (OMV 4TB + Ubuntu Server 24.04 LTS)

---

## 1. Decision Summary Table

| Category | Technology | Alternatives Considered | Decision |
|----------|-----------|------------------------|----------|
| **Backend Framework** | FastAPI (Python 3.11+) | Flask, Django, Node.js/Express | FastAPI — async-native, auto-docs |
| **Task Queue** | Celery + Redis | RQ, APScheduler, Bull (Node) | Celery — proven, feature-rich |
| **Database (Relational)** | MySQL 8.0 | PostgreSQL, SQLite, MariaDB | MySQL 8 — familiar, JSON support |
| **Vector Database** | Qdrant | Pinecone, Weaviate, Chroma | Qdrant — open-source, local deploy |
| **Frontend** | React 18 + Tailwind CSS | Vue, Svelte, vanilla JS | React — ecosystem, component model |
| **Containerization** | Docker Compose | Kubernetes, Podman | Docker Compose — simple, sufficient |
| **File Watcher** | Python `watchdog` | inotify directly, fswatch | watchdog — cross-platform, reliable |
| **Screenshot** | ffmpeg | avconv, Pillow frame extraction | ffmpeg — industry standard, precise |
| **Thumbnail AI** | Cloudflare Workers AI via free-image-generation-api | DALL-E 3, Stable Diffusion local, Midjourney | Cloudflare — free tier, sufficient quality |
| **YouTube API** | Google API Client (Python) | Direct HTTP, yt-dlp | Official client — supported, typed |
| **Telegram Bot** | python-telegram-bot | python-telegram (async), telepot | python-telegram-bot — mature, feature-rich |
| **ORM** | SQLAlchemy 2.0 | Peewee, Tortoise ORM, raw SQL | SQLAlchemy — standard, async support |
| **Migrations** | Alembic | Django migrations, raw SQL | Alembic — SQLAlchemy-native |
| **API Client** | HTTPX | requests, aiohttp | HTTPX — async, modern, typed |
| **Config Management** | Pydantic Settings | python-dotenv, dynaconf | Pydantic — validation, type safety |
| **Testing** | pytest | unittest, nose | pytest — standard, plugins |
| **Logging** | structlog + standard logging | loguru, plain logging | structlog — structured JSON logs |

---

## 2. Backend Framework: FastAPI

### 2.1 Decision

Use **FastAPI** (Python 3.11+) as the primary backend framework.

### 2.2 Rationale

| Factor | FastAPI | Flask | Django |
|--------|---------|-------|--------|
| **Async Support** | Native (`async`/`await`) | Requires extensions | Limited (Django 4.1+) |
| **Auto Documentation** | Swagger UI + ReDoc built-in | Requires Flask-RESTX | DRF or manual |
| **Type Safety** | Pydantic integration | Manual validation | DRF serializers |
| **Performance** | High (Starlette/uvicorn) | Moderate (Werkzeug) | Moderate |
| **Learning Curve** | Moderate | Low | High |
| **YouTube API Integration** | Excellent (google-api-python-client) | Good | Good |
| **File Upload Handling** | Built-in, streaming | Manual | Good |

### 2.3 Why Not Flask

Flask is simpler but lacks native async support. The system involves multiple I/O-bound operations (file watching, API calls, upload streaming) where async provides significant concurrency benefits.

### 2.4 Why Not Django

Django is too heavy for this use case. We don't need Django's admin, ORM opinions, or template system. The project is API-centric with a separate React frontend.

### 2.5 Consequences

- **Positive:** High performance for I/O-bound tasks, automatic API documentation, type-safe request/response handling.
- **Negative:** Team must be comfortable with Python async patterns (asyncio).

---

## 3. Task Queue: Celery + Redis

### 3.1 Decision

Use **Celery** with **Redis** as the broker and result backend.

### 3.2 Rationale

| Factor | Celery + Redis | RQ | APScheduler |
|--------|---------------|-----|-------------|
| **Sequential Queue** | Built-in (single worker) | Single worker | Not designed for queues |
| **Retry Logic** | Built-in with exponential backoff | Manual | Limited |
| **Priority Support** | Yes (queue routing) | No | No |
| **Scheduling** | Celery Beat | External cron | Built-in |
| **Monitoring** | Flower (built-in) | Limited | Limited |
| **YouTube Upload Tasks** | Excellent (long-running tasks) | Good | Poor |
| **Dead Letter Queue** | Built-in | Manual | No |

### 3.3 Queue Architecture

```
┌─────────────┐     ┌─────────┐     ┌──────────────┐     ┌─────────────┐
│   FastAPI   │────►│  Redis  │────►│ Celery Worker│────►│ YouTube API │
│   (API)     │     │ (Broker)│     │ (1 worker)   │     │             │
└─────────────┘     └─────────┘     └──────────────┘     └─────────────┘
                          │
                          ▼
                    ┌──────────────┐
                    │ Celery Beat  │
                    │ (Scheduler)  │
                    │ 08:00 report │
                    │ analytics    │
                    └──────────────┘
```

**Sequential Upload Guarantee:** Only **1 Celery worker** processes the upload queue. This ensures strict 1-line upload without complex locking.

### 3.4 Why Not RQ

RQ is simpler but lacks built-in scheduling (Celery Beat) and has weaker retry mechanisms. The project needs periodic tasks (analytics collection, 08:00 reports) which Celery Beat handles natively.

### 3.5 Consequences

- **Positive:** Battle-tested, extensive documentation, built-in retry and scheduling.
- **Negative:** More complex configuration than RQ; Redis is an additional dependency.

---

## 4. Database: MySQL 8.0

### 4.1 Decision

Use **MySQL 8.0** as the primary relational database.

### 4.2 Rationale

| Factor | MySQL 8 | PostgreSQL | SQLite |
|--------|---------|-----------|--------|
| **JSON Support** | Native JSON columns | JSONB (better) | Limited |
| **JSON Indexing** | Functional indexes | GIN indexes | No |
| **Familiarity** | User's team familiar | Less familiar | N/A |
| **Docker Image** | Official, well-maintained | Official | Built-in |
| **Performance** | Excellent for read-heavy | Excellent | Not for production |
| **Backup Tools** | mysqldump, Percona | pg_dump | File copy |

### 4.3 JSON Usage Strategy

MySQL 8's native JSON columns are used for:
- Metadata drafts (flexible schema for AI-generated content)
- Channel presets (templates can evolve)
- Analytics raw data (YouTube API responses)
- Queue task parameters

```sql
-- Example: Metadata draft stored as JSON
CREATE TABLE metadata_drafts (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    video_id BIGINT NOT NULL,
    draft_data JSON NOT NULL,  -- {title, description, tags, confidence_score}
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_video_id (video_id),
    INDEX idx_confidence ((CAST(draft_data->>'$.confidence_score' AS DECIMAL(5,2))))
);
```

### 4.4 Why Not PostgreSQL

PostgreSQL has superior JSON support (JSONB) and full-text search, but the team is more familiar with MySQL. The JSON usage in this project is moderate (storing drafts, not complex querying), making MySQL 8 sufficient.

### 4.5 Why Not SQLite

SQLite is not suitable for concurrent write operations (file locking). With multiple services writing (file watcher, API, Celery workers), SQLite would be a bottleneck.

### 4.6 Consequences

- **Positive:** Familiar to team, good tooling, JSON support sufficient for use case.
- **Negative:** Less powerful JSON operations than PostgreSQL; may need migration if JSON querying becomes complex.

---

## 5. Vector Database: Qdrant

### 5.1 Decision

Use **Qdrant** as the vector database for pattern recognition and similarity search.

### 5.2 Rationale

| Factor | Qdrant | Pinecone | Weaviate | Chroma |
|--------|--------|----------|----------|--------|
| **Self-Hosted** | Yes (Docker) | No (cloud only) | Yes | Yes |
| **Open Source** | Yes (Apache 2.0) | No | Yes (BSD) | Yes |
| **Resource Usage** | Low (Rust-based) | N/A (cloud) | Medium | Low |
| **Python Client** | Excellent | Good | Good | Good |
| **Filtering** | Payload filters | Metadata filters | GraphQL | Basic |
| **Persistence** | Built-in | N/A | Built-in | File-based |

### 5.3 Use Case: Pattern Recognition

Qdrant stores **performance vectors** for each video:

```python
# Example vector payload
{
    "video_id": 123,
    "channel_id": 5,
    "title_embedding": [0.12, -0.05, 0.88, ...],  # 384-dim sentence embedding
    "metadata": {
        "ctr": 3.2,
        "avd_seconds": 145,
        "views_24h": 250,
        "genre": "lofi",
        "thumbnail_style": "lofi-retro",
        "title_template": "{mood} Lofi Beats for {activity}"
    }
}
```

**Similarity Search:** Find videos with similar metadata that performed well → suggest similar approach.

### 5.4 Why Not Pinecone

Pinecone is cloud-only and requires an API key. The project runs on a home lab with self-hosted preference.

### 5.5 Consequences

- **Positive:** Fully self-hosted, no external dependency, low resource usage.
- **Negative:** Additional service to maintain (Docker container).

---

## 6. Frontend: React 18 + Tailwind CSS

### 6.1 Decision

Use **React 18** with **Tailwind CSS** for the web dashboard.

### 6.2 Rationale

| Factor | React + Tailwind | Vue + Vuetify | Svelte |
|--------|-----------------|---------------|--------|
| **Ecosystem** | Massive | Large | Growing |
| **Component Libraries** | shadcn/ui, Radix, Headless UI | Vuetify, Quasar | Limited |
| **Dashboard Patterns** | Rich (React Admin, Refine) | Moderate | Limited |
| **Tailwind Adoption** | Excellent | Good (with plugins) | Good |
| **State Management** | Zustand, RTK, Context | Pinia, Vuex | Stores |
| **Build Tool** | Vite | Vite | Vite |

### 6.3 Component Strategy

Use **shadcn/ui** as the base component library (built on Radix UI primitives + Tailwind):

| Component | Source | Reason |
|-----------|--------|--------|
| Button, Input, Select | shadcn/ui | Accessible, customizable |
| Data Table | TanStack Table | Best-in-class for queue/analytics tables |
| Charts | Recharts | React-native, customizable |
| Calendar | react-big-calendar | Schedule visualization |
| Toast Notifications | Sonner | Modern, non-intrusive |

### 6.4 Why Not Vue

Vue is excellent but React has a larger ecosystem for admin dashboards and data visualization. The team preference leans toward React for this project type.

### 6.5 Consequences

- **Positive:** Rich ecosystem, excellent component libraries, fast development.
- **Negative:** Build output is larger than Svelte; requires more boilerplate than Vue.

---

## 7. Containerization: Docker Compose

### 7.1 Decision

Use **Docker Compose** for local development and production deployment.

### 7.2 Rationale

| Factor | Docker Compose | Kubernetes | Podman |
|--------|---------------|------------|--------|
| **Complexity** | Low | High | Low |
| **Single VM** | Perfect fit | Overkill | Good |
| **Service Orchestration** | Built-in | Complex | podman-compose |
| **Volume Management** | Simple | Complex | Simple |
| **Restart Policies** | Built-in | Built-in | Built-in |
| **Team Familiarity** | High | Low | Low |

### 7.3 Service Stack

```yaml
# docker-compose.yml services
services:
  api:           # FastAPI application
  worker:        # Celery worker (upload processor)
  scheduler:     # Celery Beat (periodic tasks)
  mysql:         # MySQL 8.0
  redis:         # Redis (Celery broker + cache)
  qdrant:        # Qdrant vector database
  dashboard:     # React frontend (nginx)
  filewatcher:   # Python watchdog process
```

### 7.4 Why Not Kubernetes

Kubernetes is overkill for a single-VM deployment managing 10–30 channels. The complexity outweighs the benefits at this scale.

### 7.5 Consequences

- **Positive:** Simple deployment, easy to understand, single command (`docker compose up`).
- **Negative:** Manual scaling (not auto-scalable like K8s); single point of failure for VM.

---

## 8. File Watcher: Python `watchdog`

### 8.1 Decision

Use Python's **`watchdog`** library for file system monitoring.

### 8.2 Rationale

| Factor | watchdog | inotify (direct) | fswatch |
|--------|----------|------------------|---------|
| **Cross-Platform** | Yes | Linux only | Yes |
| **Python API** | Clean, event-driven | Low-level C | CLI only |
| **Observer Pattern** | Built-in | Manual | N/A |
| **Debouncing** | Built-in | Manual | N/A |
| **SMB/CIFS Support** | Yes (polling fallback) | No | Yes |

### 8.3 OMV Mount Consideration

OMV folders are mounted on the Ubuntu VM via **SMB/CIFS** or **NFS**. `watchdog` supports this via its `PollingObserver` fallback:

```python
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

# Try inotify first, fall back to polling for SMB mounts
try:
    observer = Observer()  # Uses inotify on Linux
except:
    observer = PollingObserver(timeout=10)  # Poll every 10 seconds
```

### 8.4 File Completion Detection

To distinguish copying-in-progress from completed files:

```python
def is_file_complete(filepath: str, stable_seconds: int = 5) -> bool:
    """Check if file size is stable for N seconds."""
    initial_size = os.path.getsize(filepath)
    time.sleep(stable_seconds)
    return os.path.getsize(filepath) == initial_size
```

### 8.5 Consequences

- **Positive:** Reliable, handles network-mounted filesystems, well-documented.
- **Negative:** Polling mode consumes more CPU than inotify (mitigated by 10-second interval).

---

## 9. Thumbnail AI: Cloudflare Workers AI

### 9.1 Decision

Use **Cloudflare Workers AI** via the **free-image-generation-api** wrapper for thumbnail generation.

### 9.2 Rationale

| Factor | Cloudflare Workers AI | DALL-E 3 | Stable Diffusion Local |
|--------|----------------------|----------|----------------------|
| **Cost** | Free tier | $0.04/image | Free (GPU required) |
| **Quality** | Good for thumbnails | Excellent | Depends on model |
| **Setup** | Simple API call | Simple API call | Complex (GPU server) |
| **Self-Hosted** | No | No | Yes |
| **Rate Limits** | Generous free tier | Pay per use | None |
| **Restyling** | Supported (img2img) | Limited | Full control |

### 9.3 API Integration

The system uses the **free-image-generation-api** (GitHub: saurav-z/free-image-generation-api) which wraps Cloudflare Workers AI:

```python
import httpx

async def generate_thumbnail(screenshot_path: str, style_prompt: str) -> bytes:
    with open(screenshot_path, "rb") as f:
        screenshot_data = f.read()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://image-generation-api-xyz.workers.dev/",
            files={"image": ("screenshot.jpg", screenshot_data, "image/jpeg")},
            data={"prompt": style_prompt, "strength": 0.7}
        )
    return response.content
```

### 9.4 Fallback Strategy

**Tier 1 — Primary:** Cloudflare Workers AI (img2img restyling)

**Tier 2 — Local PIL Fallback:** If Cloudflare AI API is unavailable, generate a styled thumbnail locally using `Pillow` (Python PIL). This has zero external dependency and runs in the same container:

```python
# app/utils/thumbnail_fallback.py
from PIL import Image, ImageDraw, ImageFont
import textwrap

def generate_pil_thumbnail(
    screenshot_path: str,
    title: str,
    channel_name: str,
    style_name: str = "default"
) -> bytes:
    """
    Local fallback thumbnail using PIL when Cloudflare AI is unavailable.
    Produces a styled overlay on the screenshot.
    """
    img = Image.open(screenshot_path).resize((1280, 720))
    
    # Dark overlay for text readability
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 120))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    
    draw = ImageDraw.Draw(img)
    
    # Channel name (top-left badge)
    draw.rectangle([(20, 20), (300, 55)], fill=(30, 30, 30, 200))
    draw.text((30, 28), channel_name.upper(), fill=(255, 255, 255), font=None)
    
    # Title (bottom area, wrapped)
    wrapped = textwrap.fill(title, width=40)
    draw.text((40, 580), wrapped, fill=(255, 255, 255), font=None, stroke_width=2, stroke_fill=(0,0,0))
    
    # Serialize to bytes
    import io
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
```

**Tier 3 — Raw Screenshot:** If PIL also fails (corrupted image), use raw screenshot directly with notification.

**Fallback Trigger Logic:**
```python
async def generate_thumbnail_with_fallback(
    screenshot_path: str,
    style_prompt: str,
    title: str,
    channel_name: str
) -> tuple[bytes, str]:  # (image_bytes, method_used)
    try:
        data = await call_cloudflare_ai(screenshot_path, style_prompt)
        return data, "cloudflare_ai"
    except Exception:
        logger.warning("cloudflare_ai_failed_using_pil_fallback")
    try:
        data = generate_pil_thumbnail(screenshot_path, title, channel_name)
        return data, "pil_fallback"
    except Exception:
        logger.error("pil_fallback_failed_using_raw_screenshot")
    with open(screenshot_path, "rb") as f:
        return f.read(), "raw_screenshot"
```

**Dependencies to add:** `Pillow` (already commonly available; add to `requirements.txt`).

**Consequences:**
- **Positive:** System never fails to produce a thumbnail; zero cost fallback.
- **Negative:** PIL-generated thumbnails are less visually polished than AI-generated ones.

---

## 10. YouTube API: Google API Client (Python)

### 10.1 Decision

Use the official **Google API Python Client** for YouTube Data API v3 and Analytics API.

### 10.2 Rationale

| Factor | Google API Client | Direct HTTP | yt-dlp |
|--------|------------------|-------------|--------|
| **Type Safety** | Partial (typed hints) | No | N/A |
| **OAuth Handling** | Built-in flow | Manual | N/A |
| **Upload Resume** | Built-in (resumable upload) | Manual | N/A |
| **Rate Limit Handling** | Built-in | Manual | N/A |
| **Documentation** | Official | Sparse | N/A |
| **Maintenance** | Google-maintained | N/A | Community |

### 10.3 Multi-Account OAuth Management

Each channel has its own GCP project and OAuth credentials:

```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

class YouTubeService:
    def __init__(self, channel_id: int, db_session):
        # Load encrypted credentials from database
        creds_data = db_session.get_credentials(channel_id)
        credentials = Credentials.from_authorized_user_info(creds_data)
        
        # Build service per channel
        self.youtube = build("youtube", "v3", credentials=credentials)
        self.analytics = build("youtubeAnalytics", "v2", credentials=credentials)
```

### 10.4 Quota Management

| API Operation | Quota Cost | Daily Limit (default) |
|--------------|-----------|----------------------|
| `videos.insert` (upload) | 1600 units | 10,000 units |
| `videos.update` (metadata) | 50 units | 10,000 units |
| `thumbnails.set` | 50 units | 10,000 units |
| `videos.list` | 1 unit | 10,000 units |
| `analytics.reports.query` | 1 unit | 10,000 units |

**Daily upload capacity per GCP project:** ~6 videos/day (1600 × 6 = 9600 units).

### 10.5 Consequences

- **Positive:** Official support, resumable uploads, built-in OAuth refresh.
- **Negative:** Quota limits require multiple GCP projects for 10–30 channels.

---

## 11. Other Technology Decisions

### 11.1 ORM: SQLAlchemy 2.0

**Decision:** SQLAlchemy 2.0 with async support (`AsyncSession`).

**Rationale:**
- Industry standard for Python ORM.
- Version 2.0 adds native async support (critical for FastAPI).
- Excellent MySQL support via `aiomysql` or `asyncmy`.
- Alembic integration for migrations.

```python
# SQLAlchemy 2.0 async pattern
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base

engine = create_async_engine("mysql+asyncmy://user:pass@localhost/ytagent")
Base = declarative_base()
```

### 11.2 API Client: HTTPX

**Decision:** HTTPX for all external API calls.

**Rationale:**
- Native async support (unlike `requests`).
- Modern API (similar to requests but async).
- Built-in connection pooling.
- Timeout and retry configuration.

### 11.3 Config Management: Pydantic Settings

**Decision:** Pydantic `BaseSettings` for configuration.

**Rationale:**
- Type-safe configuration with validation.
- Environment variable integration.
- `.env` file support.
- Default values and validation rules.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    redis_url: str = "redis://localhost:6379/0"
    telegram_bot_token: str
    
    class Config:
        env_file = ".env"
```

### 11.4 Logging: structlog

**Decision:** `structlog` for structured JSON logging.

**Rationale:**
- Structured logs are machine-parseable (essential for debugging).
- Consistent log format across services.
- Easy integration with log aggregation tools.

```python
import structlog

logger = structlog.get_logger()
logger.info("video_detected", channel="lofi_chill", filename="video_01.mp4", size_mb=500)
# Output: {"event": "video_detected", "channel": "lofi_chill", "filename": "video_01.mp4", "size_mb": 500, "timestamp": "2025-06-26T08:00:00Z"}
```

---

## 12. Infrastructure Architecture

### 12.1 Proxmox VM Layout

| VM | OS | Resources | Purpose | Storage |
|----|-----|-----------|---------|---------|
| **VM 1** | OpenMediaVault 7 | 2 vCPU, 4GB RAM | NAS — video storage | 4TB HDD (shared) |
| **VM 2** | Ubuntu Server 24.04 LTS | 4 vCPU, 8GB RAM | YTAgent services | 100GB SSD (system) |

### 12.2 Network Connectivity

```
┌─────────────────────────────────────────────────────────────┐
│                        Proxmox Host                          │
│  ┌─────────────────────┐      ┌─────────────────────────┐   │
│  │   VM 1: OMV         │      │   VM 2: Ubuntu Server   │   │
│  │   192.168.1.10      │◄────►│   192.168.1.11          │   │
│  │                     │ SMB  │                         │   │
│  │   /shared/videos/   │      │   /mnt/omv/ (mount)     │   │
│  │   4TB HDD           │      │   Docker Compose        │   │
│  │                     │      │   - FastAPI             │   │
│  │                     │      │   - Celery Worker       │   │
│  │                     │      │   - Celery Beat         │   │
│  │                     │      │   - MySQL               │   │
│  │                     │      │   - Redis               │   │
│  │                     │      │   - Qdrant              │   │
│  │                     │      │   - React Dashboard     │   │
│  └─────────────────────┘      └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Internet       │
                    │  - YouTube API  │
                    │  - Telegram API │
                    │  - Cloudflare AI│
                    └─────────────────┘
```

### 12.3 OMV Mount Configuration

```bash
# /etc/fstab on Ubuntu VM
//192.168.1.10/shared/videos /mnt/omv cifs credentials=/root/.smbcred,iocharset=utf8,sec=ntlmssp,uid=1000,gid=1000,file_mode=0755,dir_mode=0755 0 0
```

### 12.4 Resource Allocation

| Service | CPU | Memory | Notes |
|---------|-----|--------|-------|
| FastAPI | 1 vCPU | 1GB | Can scale to 2 workers |
| Celery Worker | 1 vCPU | 2GB | Upload processing is I/O bound |
| Celery Beat | 0.5 vCPU | 256MB | Lightweight scheduler |
| MySQL 8 | 1 vCPU | 2GB | With buffer pool tuning |
| Redis | 0.5 vCPU | 512MB | With maxmemory policy |
| Qdrant | 0.5 vCPU | 1GB | Vector search |
| React Dashboard (nginx) | 0.5 vCPU | 256MB | Static files |
| File Watcher | 0.5 vCPU | 256MB | Polling mode |
| **Total** | **~5.5 vCPU** | **~7.3GB** | **4 vCPU + 8GB VM sufficient** |

---

## 13. Security Decisions

### 13.1 Credential Storage

| Credential | Storage | Encryption |
|-----------|---------|------------|
| OAuth tokens (30 channels) | MySQL database | AES-256 (Fernet from cryptography) |
| Telegram bot token | Environment variable | N/A |
| Cloudflare API key | Environment variable | N/A |
| GCP client_secret.json files | Filesystem (`/secrets/`) | File permissions 600 |
| MySQL password | Environment variable | N/A |

### 13.2 API Security

- FastAPI uses JWT authentication for dashboard API.
- Rate limiting: 100 requests/minute per IP (using slowapi).
- CORS restricted to dashboard origin only.
- No API endpoints exposed publicly (internal network only).

### 13.3 Network Security

- All services communicate via Docker internal network (not exposed to host).
- Only FastAPI (port 8000) and React Dashboard (port 80/443) exposed.
- OMV mount uses SMB with credentials file (chmod 600).

---

## 14. Monitoring & Observability

### 14.1 Health Checks

| Service | Check | Interval |
|---------|-------|----------|
| FastAPI | `/health` endpoint | 30s |
| Celery Worker | Flower dashboard + heartbeat | 60s |
| MySQL | Connection check | 60s |
| Redis | `PING` | 30s |
| Qdrant | HTTP health endpoint | 60s |
| OMV Mount | Directory accessibility | 60s |

### 14.2 Alerts

| Condition | Severity | Notification |
|-----------|----------|--------------|
| Service down | Critical | Telegram |
| Queue stuck > 30 min | Warning | Telegram |
| GCP quota > 80% | Warning | Dashboard + Telegram |
| OMV storage > 80% | Warning | Telegram |
| Upload failed after 5 retries | Error | Telegram |
| Copyright claim | Critical | Telegram (immediate) |

---

## 16. OAuth Credential Isolation: `channel_credentials` Table

### 16.1 Decision

OAuth tokens are stored in a **separate `channel_credentials` table**, NOT as columns on the `channels` table. Each channel's tokens are encrypted with a **channel-specific derived key** (HKDF: base key + channel_id as salt).

### 16.2 Rationale

| Factor | Separate Table | Inline in channels |
|--------|---------------|---------------------|
| **Blast Radius** | Isolated — only one channel exposed per leaked row | All 30 channels exposed if channels table is read |
| **Key Rotation** | Can rotate per-channel without touching other tables | Full table rewrite needed |
| **Access Auditing** | Can log all credential reads separately | Mixed with general channel reads |
| **Multiple GCP Projects** | Naturally supports multiple credentials per channel | Would require JSON blob |

### 16.3 Key Derivation

```python
import os
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet
import base64

def derive_channel_key(channel_id: int) -> Fernet:
    """Derive a channel-specific encryption key from the master key."""
    master_key = os.environ["TOKEN_ENCRYPTION_KEY"].encode()
    salt = f"channel:{channel_id}".encode()  # Unique salt per channel
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"ytagent-oauth-token",
    )
    key = base64.urlsafe_b64encode(hkdf.derive(master_key))
    return Fernet(key)
```

### 16.4 Consequences

- **Positive:** Credential isolation, natural multi-project support, auditable access.
- **Negative:** Slightly more complex query (join or separate lookup vs. column read).

---

## 17. Celery + AsyncIO: Synchronous Tasks Only

### 17.1 Decision

All Celery tasks use **synchronous SQLAlchemy `Session`** (not `AsyncSession`). The `asyncio.run()` pattern inside Celery tasks is **explicitly banned**.

### 17.2 Rationale

Celery uses a **prefork process pool** by default. Each worker process has its own event loop. Calling `asyncio.run()` creates a new event loop, which conflicts with any existing loop in the process — causing `RuntimeError: This event loop is already running` or silent deadlocks under load.

| Factor | Sync Tasks (Session) | asyncio.run() in Task |
|--------|---------------------|----------------------|
| **Stability** | Rock-solid | Fragile — loop conflicts under load |
| **Simplicity** | Straightforward | Complex nested async context |
| **Performance** | Sufficient (I/O-bound) | No benefit; YouTube upload is I/O-bound |
| **Celery compatibility** | Native | Anti-pattern |

### 17.3 Implementation

Two SQLAlchemy engines coexist in the same codebase:

```python
# app/core/config.py
class Settings(BaseSettings):
    # Async URL for FastAPI routes
    database_url: str = "mysql+asyncmy://ytagent:password@mysql:3306/ytagent"
    # Sync URL for Celery tasks
    sync_database_url: str = "mysql+pymysql://ytagent:password@mysql:3306/ytagent"
```

**Additional dependency:** `pymysql` (`pip install pymysql`).

### 17.4 Consequences

- **Positive:** No asyncio conflicts; tasks are simple and debuggable.
- **Negative:** Two SQLAlchemy engines in config (minor complexity); PyMySQL is an additional dependency.

---

## 18. GCP Quota Auto-Rotation

### 18.1 Decision

When a GCP project's daily quota is exhausted, the upload queue **automatically switches** to the next available GCP project for that channel (if one exists) instead of stopping the queue.

### 18.2 Implementation

See ARCHITECTURE.md Section 7.3 for the full flow diagram.

```python
def get_active_gcp_project(db: Session, channel_id: int) -> GCPProject:
    """Get the next available GCP project for a channel with quota remaining."""
    today = date.today()
    project = db.execute(
        select(GCPProject)
        .where(GCPProject.channel_id == channel_id)
        .where(GCPProject.status == "active")
        .where(GCPProject.last_reset == today)
        .where(GCPProject.quota_used < GCPProject.quota_limit)
        .order_by(GCPProject.id.asc())  # prefer first registered project
        .limit(1)
    ).scalar_one_or_none()
    if not project:
        raise AllProjectsExhaustedError(
            f"All GCP projects for channel {channel_id} have exhausted quota today."
        )
    return project
```

### 18.3 Daily Reset Celery Beat Task

```python
"reset-gcp-quota": {
    "task": "tasks.maintenance.reset_daily_gcp_quota",
    "schedule": crontab(hour="0", minute="5"),  # 00:05 UTC = 07:05 WIB
},
```

### 18.4 Consequences

- **Positive:** No manual intervention needed when one project hits quota; queue continues automatically.
- **Negative:** Requires each channel to have multiple GCP projects configured; first-project setup is unchanged.

---

## 15. Decision Change Log

| Date | Decision | Change | Reason |
|------|----------|--------|--------|
| 2025-06-26 | Thumbnail AI | Cloudflare Workers AI (free) | User explicitly rejected DALL-E fallback; free tier sufficient |
| 2025-06-26 | Auto-approve | Conditional (per-channel toggle) | User wants control; auto-approve only after confidence established |
| 2025-06-26 | Scheduling | Preferred time as guideline, not hard rule | User confirmed: if queue clear, next video starts immediately |
| 2025-06-26 | Reporting | Accumulative at 08:00 WIB | User preference: daily digest instead of per-video alerts |
| 2025-06-26 | Storage | No auto-cleanup | User explicitly wants to keep all files on OMV |
| 2026-06-23 | Thumbnail fallback | Added PIL local fallback (Tier 2) | Third-party `free-image-generation-api` has no SLA; PIL ensures continuity |
| 2026-06-23 | Credential storage | Moved OAuth to `channel_credentials` table | Blast radius isolation; per-channel key derivation via HKDF |
| 2026-06-23 | Celery + asyncio | Banned `asyncio.run()` in tasks; use sync Session | Prevents event loop conflicts in prefork worker pool |
| 2026-06-23 | GCP quota rotation | Auto-switch project on quota exceeded | Prevents queue halt when one project is exhausted |
| 2026-06-23 | thumbnail_first_time | Replaced boolean with `thumbnail_style_confirmed_at TIMESTAMP` | Self-auditing, resettable, no boolean fragility |
| 2026-06-23 | Retry count | Standardized to max_retries=5 everywhere | Was inconsistent between AGENT_RULES ("5-10") and code (5) |
| 2026-06-23 | Log rotation | System logs purged at 30 days (weekly Celery task) | Prevent unbounded table growth; 90 days was too long |
