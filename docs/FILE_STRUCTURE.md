# FILE_STRUCTURE.md

## YTAgent — Project File Structure

> **Version:** 1.0.0
> **Date:** 2025-06-26
> **Status:** Approved
> **Deployment:** Docker Compose on Ubuntu Server VM

---

## 1. Repository Root

```
ytagent/
├── 📁 app/                          # FastAPI backend application
├── 📁 dashboard/                    # React frontend
├── 📁 services/                     # Standalone background services
│   └── filewatcher/                 # OMV file watcher
├── 📁 scripts/                      # Utility & setup scripts
├── 📁 docs/                         # Documentation (this folder)
├── 📁 docker/                       # Docker configuration files
├── 📁 secrets/                      # Sensitive credentials (gitignored)
│   └── gcp/                         # client_secret.json files per channel
├── 📁 tests/                        # Test suites
├── 📄 docker-compose.yml            # Main orchestration file
├── 📄 docker-compose.dev.yml        # Development overrides
├── 📄 .env.example                  # Environment variables template
├── 📄 .env                          # Actual environment variables (gitignored)
├── 📄 .gitignore                    # Git ignore rules
├── 📄 Makefile                      # Common commands
└── 📄 README.md                     # Project overview & quick start
```

---

## 2. Backend (`app/`)

```
app/
├── 📁 api/                          # FastAPI route handlers (Controllers)
│   ├── __init__.py
│   ├── dependencies.py              # FastAPI dependencies (DB session, auth)
│   ├── v1/                          # API Version 1
│   │   ├── __init__.py
│   │   ├── router.py                # Main v1 router aggregation
│   │   ├── channels.py              # Channel CRUD endpoints
│   │   ├── videos.py                # Video lifecycle endpoints
│   │   ├── queue.py                 # Queue management endpoints
│   │   ├── analytics.py             # Analytics data endpoints
│   │   ├── uploads.py               # Upload trigger endpoints
│   │   ├── notifications.py         # Notification endpoints
│   │   ├── insights.py              # AI insight endpoints
│   │   ├── users.py                 # User management endpoints
│   │   ├── gcp.py                   # GCP project/quota endpoints
│   │   ├── logs.py                  # System log endpoints
│   │   └── health.py                # Health check endpoint
│   └── deps.py                      # Shared dependency injection
│
├── 📁 core/                         # Core configuration & utilities
│   ├── __init__.py
│   ├── config.py                    # Pydantic Settings (env vars)
│   ├── database.py                  # SQLAlchemy engine & session
│   ├── security.py                  # JWT auth, password hashing, encryption
│   ├── logging.py                   # structlog configuration
│   ├── exceptions.py                # Custom exception classes
│   ├── constants.py                 # System-wide constants
│   └── events.py                    # Startup/shutdown event handlers
│
├── 📁 models/                       # SQLAlchemy ORM models
│   ├── __init__.py                  # Model exports
│   ├── base.py                      # Base class & mixins
│   ├── user.py                      # users table
│   ├── channel.py                   # channels table
│   ├── channel_credentials.py       # channel_credentials table (OAuth isolation)
│   ├── gcp_project.py               # gcp_projects table
│   ├── video.py                     # videos table
│   ├── thumbnail_draft.py           # thumbnail_drafts table
│   ├── metadata_draft.py            # metadata_drafts table
│   ├── queue_task.py                # queue_tasks table
│   ├── analytics_record.py          # analytics_records table
│   ├── performance_insight.py       # performance_insights table
│   ├── system_log.py                # system_logs table
│   └── notification_history.py      # notification_history table
│
├── 📁 schemas/                      # Pydantic request/response schemas
│   ├── __init__.py
│   ├── base.py                      # Base schema classes
│   ├── user.py                      # User schemas
│   ├── channel.py                   # Channel schemas
│   ├── video.py                     # Video schemas
│   ├── thumbnail.py                 # Thumbnail draft schemas
│   ├── metadata.py                  # Metadata draft schemas
│   ├── queue.py                     # Queue task schemas
│   ├── analytics.py                 # Analytics schemas
│   ├── insight.py                   # Performance insight schemas
│   ├── notification.py              # Notification schemas
│   └── log.py                       # Log schemas
│
├── 📁 services/                     # Business logic layer
│   ├── __init__.py
│   ├── base.py                      # Base service class
│   ├── channel_service.py           # Channel CRUD operations
│   ├── video_service.py             # Video lifecycle management
│   ├── ingestion_service.py         # File detection & processing
│   ├── thumbnail_service.py         # AI thumbnail generation
│   ├── metadata_service.py          # AI metadata generation
│   ├── upload_service.py            # YouTube upload orchestration (async, for API)
│   ├── upload_service_sync.py       # YouTube upload (SYNC, for Celery tasks)
│   ├── queue_service.py             # Queue management logic
│   ├── analytics_service.py         # Analytics collection & storage
│   ├── insight_service.py           # AI insight generation
│   ├── notification_service.py      # Telegram notification logic
│   ├── gcp_service.py               # GCP quota & credential management
│   ├── qdrant_service.py            # Vector database operations
│   └── log_service.py               # Structured logging operations
│
├── 📁 tasks/                        # Celery background tasks
│   ├── __init__.py
│   ├── celery_app.py                # Celery app configuration
│   ├── upload.py                    # YouTube upload tasks (sync Session)
│   ├── analytics.py                 # Analytics collection tasks
│   ├── notifications.py             # Notification delivery tasks
│   ├── ingestion.py                 # Periodic OMV sync tasks
│   ├── insights.py                  # AI insight generation tasks
│   └── maintenance.py               # Cleanup tasks: log rotation, GCP quota reset, backup verify
│
├── 📁 utils/                        # Utility functions
│   ├── __init__.py
│   ├── ffmpeg.py                    # ffmpeg/ffprobe wrappers
│   ├── youtube_api.py               # YouTube Data API client wrapper
│   ├── telegram_api.py              # Telegram Bot API wrapper
│   ├── cloudflare_ai.py             # Cloudflare Workers AI API wrapper
│   ├── thumbnail_fallback.py        # PIL-based local thumbnail fallback (Tier 2)
│   ├── credential_crypto.py         # HKDF key derivation + Fernet encrypt/decrypt
│   ├── file_utils.py                # File system utilities
│   ├── validators.py                # Input validation helpers
│   ├── formatters.py                # Data formatting (time, size, etc.)
│   └── embeddings.py                # Text embedding generation for Qdrant
│
├── 📄 main.py                       # FastAPI application entry point
├── 📄 Dockerfile                    # Production Docker image
├── 📄 Dockerfile.worker             # Celery worker Docker image
├── 📄 pyproject.toml                # Python dependencies & project config
├── 📄 requirements.txt              # Pinned Python dependencies
└── 📄 alembic.ini                   # Alembic migration configuration
```

---

## 3. Frontend (`dashboard/`)

```
dashboard/
├── 📁 public/                       # Static assets
│   ├── favicon.ico
│   ├── logo.svg
│   └── robots.txt
│
├── 📁 src/
│   ├── 📁 components/               # Reusable UI components
│   │   ├── ui/                      # shadcn/ui base components
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── input.tsx
│   │   │   ├── textarea.tsx
│   │   │   ├── select.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── dropdown-menu.tsx
│   │   │   ├── table.tsx
│   │   │   ├── tabs.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── avatar.tsx
│   │   │   ├── toast.tsx            # Sonner wrapper
│   │   │   ├── skeleton.tsx
│   │   │   ├── progress.tsx
│   │   │   ├── calendar.tsx
│   │   │   └── ...
│   │   │
│   │   ├── layout/                  # Layout components
│   │   │   ├── Sidebar.tsx          # Main navigation sidebar
│   │   │   ├── Header.tsx           # Top header bar
│   │   │   ├── ChannelSelector.tsx  # Channel dropdown selector
│   │   │   └── Layout.tsx           # Main layout wrapper
│   │   │
│   │   ├── video/                   # Video-related components
│   │   │   ├── VideoCard.tsx        # Video card (collapsed/expanded)
│   │   │   ├── VideoGrid.tsx        # Grid of video cards
│   │   │   ├── VideoDetailTabs.tsx  # Tab navigation for video detail
│   │   │   ├── MetadataEditor.tsx   # Metadata form editor
│   │   │   ├── ThumbnailCarousel.tsx # Thumbnail selection carousel
│   │   │   ├── ThumbnailPreview.tsx # Full-size thumbnail modal
│   │   │   └── ScreenshotViewer.tsx # Frame-30 screenshot viewer
│   │   │
│   │   ├── queue/                   # Queue components
│   │   │   ├── QueueItem.tsx        # Single queue item
│   │   │   ├── QueueList.tsx        # List of queue items
│   │   │   ├── ActiveUpload.tsx     # Currently uploading item
│   │   │   └── QueueStats.tsx       # Queue statistics summary
│   │   │
│   │   ├── analytics/               # Analytics components
│   │   │   ├── ViewsChart.tsx       # Views trend line chart
│   │   │   ├── CTRChart.tsx         # CTR bar chart
│   │   │   ├── AVDChart.tsx         # AVD comparison chart
│   │   │   ├── PerformanceTable.tsx # Video performance data table
│   │   │   ├── ChannelStatsCards.tsx # Summary stat cards
│   │   │   └── InsightCard.tsx      # AI insight display card
│   │   │
│   │   ├── channel/                 # Channel management components
│   │   │   ├── ChannelCard.tsx      # Channel status card (dashboard)
│   │   │   ├── ChannelGrid.tsx      # Grid of channel cards
│   │   │   ├── ChannelForm.tsx      # Channel settings form
│   │   │   ├── PresetEditor.tsx     # Metadata preset editor
│   │   │   ├── ThumbnailStyleEditor.tsx # Thumbnail style configuration
│   │   │   └── GCPConfigForm.tsx    # GCP credentials form
│   │   │
│   │   ├── common/                  # Shared/common components
│   │   │   ├── StatusBadge.tsx      # Status indicator badge
│   │   │   ├── LoadingSpinner.tsx   # Loading state spinner
│   │   │   ├── EmptyState.tsx       # Empty state illustration
│   │   │   ├── ErrorBoundary.tsx    # React error boundary
│   │   │   ├── ConfirmDialog.tsx    # Confirmation dialog
│   │   │   ├── TimePicker.tsx       # Time picker component
│   │   │   ├── FileSizeDisplay.tsx  # Human-readable file size
│   │   │   ├── DurationDisplay.tsx  # Human-readable duration
│   │   │   └── RelativeTime.tsx     # "2 minutes ago" display
│   │   │
│   │   └── schedule/                # Schedule components
│   │       ├── ScheduleCalendar.tsx # Monthly calendar view
│   │       ├── ScheduleDay.tsx      # Single day cell
│   │       └── ScheduleLegend.tsx   # Channel color legend
│   │
│   ├── 📁 hooks/                    # Custom React hooks
│   │   ├── useChannels.ts           # Channel data fetching
│   │   ├── useVideos.ts             # Video data fetching
│   │   ├── useQueue.ts              # Queue data fetching
│   │   ├── useAnalytics.ts          # Analytics data fetching
│   │   ├── useInsights.ts           # Insights data fetching
│   │   ├── useLogs.ts               # Logs data fetching
│   │   ├── useChannelContext.ts     # Selected channel context
│   │   ├── useApi.ts                # Generic API client hook
│   │   ├── useWebSocket.ts          # Real-time updates (future)
│   │   └── useLocalStorage.ts       # localStorage persistence
│   │
│   ├── 📁 stores/                   # Zustand state stores
│   │   ├── channelStore.ts          # Channel selection & list
│   │   ├── videoStore.ts            # Video list & detail
│   │   ├── queueStore.ts            # Queue state
│   │   ├── analyticsStore.ts        # Analytics data
│   │   ├── uiStore.ts               # UI state (sidebar, modals)
│   │   └── authStore.ts             # Authentication state
│   │
│   ├── 📁 pages/                    # Page components (route-level)
│   │   ├── DashboardPage.tsx        # Global dashboard
│   │   ├── StagingPage.tsx          # Staging area
│   │   ├── VideoDetailPage.tsx      # Video detail
│   │   ├── QueuePage.tsx            # Queue manager
│   │   ├── SchedulePage.tsx         # Schedule calendar
│   │   ├── AnalyticsPage.tsx        # Analytics
│   │   ├── ChannelSettingsPage.tsx  # Channel settings
│   │   ├── ChannelListPage.tsx      # Channel list
│   │   ├── LogsPage.tsx             # System logs
│   │   ├── GCPManagerPage.tsx       # GCP quota manager
│   │   └── SettingsPage.tsx         # Global settings
│   │
│   ├── 📁 lib/                      # Library & utility code
│   │   ├── api.ts                   # Axios/Fetch API client setup
│   │   ├── queryClient.ts           # TanStack Query client config
│   │   ├── utils.ts                 # cn() and other utilities
│   │   ├── constants.ts             # Frontend constants
│   │   └── types.ts                 # Shared TypeScript types
│   │
│   ├── 📁 styles/                   # Global styles
│   │   └── globals.css              # Tailwind directives + custom CSS
│   │
│   ├── 📄 App.tsx                   # Root component with routing
│   ├── 📄 main.tsx                  # Entry point (ReactDOM)
│   └── 📄 router.tsx                # React Router configuration
│
├── 📄 index.html                    # HTML entry point
├── 📄 vite.config.ts                # Vite build configuration
├── 📄 tailwind.config.ts            # Tailwind CSS configuration
├── 📄 tsconfig.json                 # TypeScript configuration
├── 📄 tsconfig.node.json            # TypeScript for Node (Vite)
├── 📄 package.json                  # NPM dependencies
├── 📄 package-lock.json             # Locked dependency versions
└── 📄 Dockerfile                    # Production Docker image (nginx)
```

---

## 4. File Watcher Service (`services/filewatcher/`)

```
services/filewatcher/
├── 📁 src/
│   ├── __init__.py
│   ├── main.py                      # Entry point
│   ├── watcher.py                   # watchdog event handlers
│   ├── detector.py                  # File completion detection logic
│   ├── api_client.py                # HTTP client for FastAPI
│   └── config.py                    # Service configuration
├── 📄 Dockerfile                    # Service Docker image
├── 📄 requirements.txt              # Python dependencies
└── 📄 README.md                     # Service documentation
```

---

## 5. Docker Configuration (`docker/`)

```
docker/
├── 📄 mysql.cnf                     # MySQL custom configuration
├── 📄 redis.conf                    # Redis custom configuration
├── 📄 nginx.conf                    # Nginx configuration for dashboard
├── 📄 filewatcher-entrypoint.sh     # File watcher startup script
└── 📄 api-entrypoint.sh             # API service startup script
```

---

## 6. Scripts (`scripts/`)

```
scripts/
├── 📄 setup.sh                      # One-time environment setup
├── 📄 setup-gcp.py                  # GCP OAuth setup helper
├── 📄 setup-telegram.py             # Telegram bot setup helper
├── 📄 create-channel.py             # Create new channel with presets
├── 📄 backup-db.sh                  # Database backup script
├── 📄 restore-db.sh                 # Database restore script
├── 📄 reset-queue.sh                # Emergency queue reset
├── 📄 health-check.sh               # System health check
└── 📄 logs.sh                       # View logs by service
```

---

## 7. Tests (`tests/`)

```
tests/
├── 📁 unit/                         # Unit tests
│   ├── 📁 services/                 # Service layer tests
│   │   ├── test_channel_service.py
│   │   ├── test_video_service.py
│   │   ├── test_thumbnail_service.py
│   │   ├── test_metadata_service.py
│   │   ├── test_upload_service.py
│   │   └── test_queue_service.py
│   ├── 📁 utils/                    # Utility tests
│   │   ├── test_ffmpeg.py
│   │   ├── test_validators.py
│   │   └── test_formatters.py
│   └── 📁 models/                   # Model tests
│       └── test_video_model.py
│
├── 📁 integration/                  # Integration tests
│   ├── test_api_endpoints.py        # FastAPI endpoint tests
│   ├── test_database.py             # Database operations
│   ├── test_celery_tasks.py         # Celery task tests
│   └── test_file_watcher.py         # File detection tests
│
├── 📁 e2e/                          # End-to-end tests (future)
│   └── (Playwright/Cypress)
│
├── 📄 conftest.py                   # pytest configuration & fixtures
├── 📄 pytest.ini                    # pytest settings
└── 📄 .coveragerc                   # Coverage configuration
```

---

## 8. Secrets (`secrets/`)

**⚠️ This directory is `.gitignore`d and never committed.**

```
secrets/
└── 📁 gcp/                          # GCP client secrets
    ├── 📄 channel-lofi-01.json      # Lofi Chill GCP client_secret
    ├── 📄 channel-jazz-01.json      # Oud Jazz GCP client_secret
    ├── 📄 channel-ambient-01.json   # Ambient Vibes GCP client_secret
    └── 📄 ...                       # One per channel
```

**Security Notes:**
- Files chmod 600 (owner read/write only)
- Mounted as read-only volume in Docker containers
- Backed up separately from codebase

---

## 9. Configuration Files

### 9.1 `.env.example`

```bash
# Copy to .env and fill in values

# MySQL
MYSQL_ROOT_PASSWORD=change_me
MYSQL_USER=ytagent
MYSQL_PASSWORD=change_me

# Redis
REDIS_URL=redis://redis:6379/0

# FastAPI
SECRET_KEY=your-jwt-secret-key-here
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false

# Telegram
TELEGRAM_BOT_TOKEN=your-bot-token-from-botfather

# Cloudflare AI
CF_AI_URL=https://your-worker.workers.dev/

# Encryption
TOKEN_ENCRYPTION_KEY=your-fernet-key-base64

# OMV
OMV_MOUNT_PATH=/mnt/omv

# Timezone
TZ=Asia/Jakarta

# Supervisor Telegram ID (for notifications)
SUPERVISOR_TELEGRAM_ID=123456789
```

### 9.2 `.gitignore`

```gitignore
# Environment
.env
.env.local
.env.production

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/
*.egg-info/
dist/
build/

# Node
node_modules/
dist/
build/
*.log
npm-debug.log*

# Secrets
secrets/
*.pem
*.key

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Testing
.coverage
htmlcov/
.pytest_cache/

# Docker
*.env.docker

# Database
*.sql
*.dump

# Logs
logs/
*.log
```

---

## 10. Makefile Commands

```makefile
# Makefile — Common development commands

.PHONY: up down build logs test migrate shell

# Docker Compose
up:
	docker compose -f docker-compose.yml up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

# Development
dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Database
migrate:
	docker compose exec api alembic upgrade head

migrate-down:
	docker compose exec api alembic downgrade -1

migrate-create:
	docker compose exec api alembic revision --autogenerate -m "$(message)"

# Testing
test:
	docker compose exec api pytest tests/ -v

test-coverage:
	docker compose exec api pytest tests/ --cov=app --cov-report=html

# Shell access
shell-api:
	docker compose exec api bash

shell-db:
	docker compose exec mysql mysql -u ytagent -p

shell-redis:
	docker compose exec redis redis-cli

# Maintenance
backup:
	./scripts/backup-db.sh

health:
	./scripts/health-check.sh

clean:
	docker compose down -v
	docker system prune -f
```

---

## 11. File Naming Conventions

| Category | Convention | Example |
|----------|-----------|---------|
| Python modules | snake_case | `channel_service.py` |
| Python classes | PascalCase | `ChannelService` |
| Python functions | snake_case | `get_channel_by_id()` |
| Python constants | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT = 5` |
| React components | PascalCase | `VideoCard.tsx` |
| React hooks | camelCase with `use` prefix | `useChannelContext.ts` |
| CSS/SCSS | kebab-case | `video-card.css` |
| Docker files | lowercase | `dockerfile`, `docker-compose.yml` |
| Environment files | UPPER_SNAKE_CASE keys | `DATABASE_URL` |
| Test files | `test_` prefix | `test_channel_service.py` |
| Migration files | timestamp + description | `001_initial_schema.py` |
