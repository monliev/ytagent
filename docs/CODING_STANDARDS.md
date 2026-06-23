# CODING_STANDARDS.md

## YTAgent — Coding Standards & Development Guidelines

> **Version:** 1.0.0
> **Date:** 2025-06-26
> **Applies To:** Python (FastAPI/Celery), TypeScript/React (Dashboard), Docker

---

## 1. General Principles

### 1.1 Core Tenets

| Principle | Meaning |
|-----------|---------|
| **Readability First** | Code is read 10x more than it's written. Prioritize clarity. |
| **Explicit over Implicit** | Avoid magic. Be explicit about behavior and side effects. |
| **Type Safety** | Use type hints everywhere (Python) and strict TypeScript (React). |
| **Fail Fast** | Validate early, raise errors immediately, never swallow exceptions silently. |
| **DRY (Don't Repeat Yourself)** | Extract common logic into reusable functions/services. |
| **Single Responsibility** | Each function/class/module does one thing and does it well. |

### 1.2 Code Review Checklist

Before submitting code, ensure:

- [ ] All functions have type hints/docstrings
- [ ] No hardcoded credentials or secrets
- [ ] Error handling covers all failure paths
- [ ] Logging added for significant operations
- [ ] Unit tests written for business logic
- [ ] No `print()` statements (use logging)
- [ ] No commented-out code
- [ ] No debugging breakpoints left in code

---

## 2. Python Standards (FastAPI / Celery)

### 2.1 Code Style: PEP 8 + Ruff

Use **Ruff** for linting and formatting (replaces flake8, black, isort):

```toml
# pyproject.toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]
ignore = ["E501"]  # Line length handled by formatter

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### 2.2 Type Hints: Mandatory

Every function parameter and return type must be annotated:

```python
# ✅ CORRECT
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

async def get_channel_by_id(
    db: AsyncSession,
    channel_id: int
) -> Optional[Channel]:
    """Fetch a channel by its ID.
    
    Args:
        db: Database session.
        channel_id: The channel ID to look up.
        
    Returns:
        The Channel if found, None otherwise.
        
    Raises:
        DatabaseError: If a database error occurs.
    """
    result = await db.execute(
        select(Channel).where(Channel.id == channel_id)
    )
    return result.scalar_one_or_none()

# ❌ INCORRECT — missing type hints
def get_channel(db, channel_id):
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    return result.scalar_one_or_none()
```

### 2.3 Docstrings: Google Style

All public functions and classes must have Google-style docstrings:

```python
class VideoService:
    """Manages video lifecycle from detection to upload.
    
    This service coordinates between file ingestion, AI generation,
    and upload orchestration.
    
    Attributes:
        db: Async database session.
        queue_service: Queue management service.
        notification_service: Telegram notification service.
    """
    
    async def process_new_video(
        self,
        file_path: str,
        channel_id: int
    ) -> Video:
        """Process a newly detected video file.
        
        Steps:
            1. Validate file integrity.
            2. Extract screenshot at second 30.
            3. Generate thumbnail options.
            4. Generate metadata draft.
            5. Notify supervisor.
        
        Args:
            file_path: Absolute path to the video file on OMV.
            channel_id: ID of the channel this video belongs to.
            
        Returns:
            The created Video record.
            
        Raises:
            VideoValidationError: If file is corrupted or invalid.
            ThumbnailGenerationError: If AI thumbnail generation fails.
        """
        pass
```

### 2.4 Async/Await Patterns

FastAPI and all I/O operations use async/await:

```python
# ✅ CORRECT — async database operations
async def list_videos(
    db: AsyncSession,
    channel_id: int,
    status: VideoStatus
) -> list[Video]:
    result = await db.execute(
        select(Video)
        .where(Video.channel_id == channel_id)
        .where(Video.status == status)
        .order_by(Video.created_at.desc())
    )
    return result.scalars().all()

# ✅ CORRECT — async external API calls
async def generate_thumbnail(
    screenshot_path: str,
    style_prompt: str
) -> bytes:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            settings.cf_ai_url,
            files={"image": open(screenshot_path, "rb")},
            data={"prompt": style_prompt}
        )
        response.raise_for_status()
        return response.content

# ❌ INCORRECT — blocking I/O in async context
async def bad_example():
    response = requests.post(url, data=data)  # requests is blocking!
    return response.json()
```

### 2.5 Error Handling

Use custom exceptions with proper inheritance:

```python
# app/core/exceptions.py

class YTAgentException(Exception):
    """Base exception for all YTAgent errors."""
    pass

class VideoValidationError(YTAgentException):
    """Raised when a video file fails validation."""
    pass

class ThumbnailGenerationError(YTAgentException):
    """Raised when AI thumbnail generation fails."""
    pass

class UploadError(YTAgentException):
    """Raised when YouTube upload fails."""
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable

class QuotaExceededError(YTAgentException):
    """Raised when YouTube API quota is exceeded."""
    pass

class CopyrightClaimError(YTAgentException):
    """Raised when a copyright claim is detected."""
    pass
```

**Error handling pattern:**

```python
# ✅ CORRECT — specific exception handling with logging
async def upload_video(video_id: int) -> None:
    try:
        video = await video_service.get(video_id)
        await youtube_client.upload(video)
    except QuotaExceededError as exc:
        logger.warning("quota_exceeded", video_id=video_id, error=str(exc))
        await queue_service.pause_channel(video.channel_id)
        await notification_service.notify_quota_warning(video.channel_id)
        raise  # Re-raise for Celery retry
    except UploadError as exc:
        if exc.retryable:
            logger.warning("upload_retryable", video_id=video_id, error=str(exc))
            raise  # Let Celery handle retry
        logger.error("upload_failed", video_id=video_id, error=str(exc))
        await notification_service.notify_upload_failed(video_id)
    except CopyrightClaimError as exc:
        logger.critical("copyright_claim", video_id=video_id, error=str(exc))
        await queue_service.pause_all_queues()
        await notification_service.notify_copyright_alert(video_id)
```

### 2.6 Logging Standards

Use **structlog** for structured JSON logging:

```python
import structlog

logger = structlog.get_logger()

# ✅ CORRECT — structured logging with context
logger.info(
    "video_detected",
    channel_id=channel.id,
    channel_name=channel.name,
    filename=filename,
    file_size_mb=file_size / 1024 / 1024,
    source="file_watcher"
)

# ✅ CORRECT — different log levels
logger.debug("ffmpeg_command", command=cmd, args=args)
logger.info("upload_started", video_id=video.id, youtube_video_id=video.youtube_id)
logger.warning("retry_attempt", video_id=video.id, attempt=attempt, max_retries=5)
logger.error("upload_failed", video_id=video.id, error=error_msg, retryable=True)
logger.critical("copyright_claim_detected", video_id=video.id, channel_id=channel.id)

# ❌ INCORRECT — string formatting, not structured
logger.info(f"Video {video_id} detected in channel {channel_name}")
```

**Log output format:**
```json
{
  "event": "video_detected",
  "channel_id": 5,
  "channel_name": "lofi_chill",
  "filename": "study_beats_01.mp4",
  "file_size_mb": 450.5,
  "source": "file_watcher",
  "timestamp": "2025-06-26T08:00:00+07:00",
  "level": "info"
}
```

### 2.7 Database Access Patterns

**Repository/Service Pattern:**

```python
# app/services/channel_service.py

class ChannelService:
    """Business logic for channel management."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get(self, channel_id: int) -> Channel:
        """Get channel by ID."""
        channel = await self.db.get(Channel, channel_id)
        if not channel:
            raise NotFoundError(f"Channel {channel_id} not found")
        return channel
    
    async def list_active(self) -> list[Channel]:
        """List all active channels."""
        result = await self.db.execute(
            select(Channel).where(Channel.is_active == True)
        )
        return result.scalars().all()
    
    async def update_preset(
        self,
        channel_id: int,
        preset_data: ChannelPresetUpdate
    ) -> Channel:
        """Update channel preset. Requires manual Supervisor approval tracking."""
        channel = await self.get(channel_id)
        
        # Update fields
        channel.preset_title_template = preset_data.title_template
        channel.preset_tags = preset_data.tags
        channel.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(channel)
        
        logger.info("channel_preset_updated", channel_id=channel_id)
        return channel
```

**Dependency Injection (FastAPI):**

```python
# app/api/dependencies.py

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db() -> AsyncSession:
    """Yield database session for request lifecycle."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_channel_service(
    db: AsyncSession = Depends(get_db)
) -> ChannelService:
    return ChannelService(db)

# Usage in routes
@router.get("/channels/{channel_id}")
async def get_channel(
    channel_id: int,
    service: ChannelService = Depends(get_channel_service)
):
    return await service.get(channel_id)
```

### 2.8 Celery Task Patterns

```python
# app/tasks/upload.py

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import structlog

logger = structlog.get_logger()

@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=300,      # 5 minutes
    retry_backoff=True,           # Exponential backoff
    retry_backoff_max=3600,       # Max 1 hour
    retry_jitter=True,            # Add randomness to prevent thundering herd
)
def upload_video_to_youtube(self, video_id: int) -> dict:
    """Upload video to YouTube.
    
    This task runs sequentially (single worker) to ensure
    only one upload is active at any time.

    IMPORTANT: Uses a SYNCHRONOUS SQLAlchemy Session, NOT AsyncSession.
    Celery tasks run in a prefork process pool — using asyncio.run() here
    will cause event loop conflicts. See AGENT_RULES.md Section 6.4 and
    TECH_DECISIONS.md Section 17 for the canonical rationale.
    
    Args:
        video_id: ID of the video to upload.
        
    Returns:
        Dict with upload result and YouTube video ID.
        
    Raises:
        MaxRetriesExceededError: After all retries are exhausted.
    """
    logger.info("upload_task_started", video_id=video_id, attempt=self.request.retries)
    
    # Use sync engine — separate URL from async FastAPI engine
    # Configured as settings.sync_database_url = "mysql+pymysql://..."
    from app.core.config import settings
    engine = create_engine(settings.sync_database_url)
    
    try:
        with Session(engine) as db:
            from app.models.video import Video
            from app.models.channel import Channel
            from app.services.upload_service_sync import UploadServiceSync
            
            video = db.get(Video, video_id)
            if not video:
                logger.error("upload_task_video_not_found", video_id=video_id)
                return {"error": "video_not_found"}
            
            upload_service = UploadServiceSync(db)
            result = upload_service.upload(video)  # sync upload logic
            
            logger.info("upload_task_completed",
                       video_id=video_id,
                       youtube_id=result["youtube_id"])
            return result
        
    except QuotaExceededError as exc:
        logger.warning("upload_quota_exceeded", video_id=video_id)
        raise self.retry(exc=exc, countdown=3600)  # Retry in 1 hour
        
    except UploadError as exc:
        if exc.retryable and self.request.retries < self.max_retries:
            logger.warning("upload_retrying",
                         video_id=video_id,
                         attempt=self.request.retries + 1,
                         error=str(exc))
            raise self.retry(exc=exc)
        
        logger.error("upload_permanently_failed",
                    video_id=video_id,
                    total_attempts=self.request.retries + 1)
        raise
        
    except Exception as exc:
        logger.exception("upload_unexpected_error", video_id=video_id)
        raise
    
    finally:
        engine.dispose()  # Release connection pool on task exit


# ❌ WRONG — NEVER DO THIS in a Celery task:
# def upload_video_to_youtube(self, video_id: int):
#     async def _do_upload():
#         async with AsyncSessionLocal() as db:  # asyncio context
#             ...
#     return asyncio.run(_do_upload())  # Causes event loop conflict!
```

---

## 3. TypeScript/React Standards

### 3.1 TypeScript Configuration

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

### 3.2 Component Structure

```tsx
// ✅ CORRECT — Functional component with proper typing
import { useState, useCallback } from "react";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/common/StatusBadge";
import { useVideoStore } from "@/stores/videoStore";
import type { Video } from "@/lib/types";

interface VideoCardProps {
  video: Video;
  expanded?: boolean;
  onApprove: (videoId: number) => void;
  onEdit: (videoId: number) => void;
}

export function VideoCard({ 
  video, 
  expanded = false, 
  onApprove, 
  onEdit 
}: VideoCardProps): JSX.Element {
  const [isExpanded, setIsExpanded] = useState(expanded);
  
  const handleApprove = useCallback(() => {
    onApprove(video.id);
  }, [video.id, onApprove]);
  
  return (
    <Card className="w-full">
      <CardHeader className="flex flex-row items-center justify-between">
        <div className="flex items-center gap-3">
          <StatusBadge status={video.status} />
          <h3 className="font-semibold">{video.currentTitle}</h3>
        </div>
        <Button 
          variant="ghost" 
          size="sm"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          {isExpanded ? "Collapse" : "Expand"}
        </Button>
      </CardHeader>
      
      {isExpanded && (
        <CardContent>
          {/* Expanded content */}
          <div className="flex gap-4">
            <img 
              src={video.thumbnailUrl} 
              alt={`Thumbnail for ${video.currentTitle}`}
              className="w-48 h-28 object-cover rounded"
            />
            <div className="flex-1">
              <p className="text-sm text-muted-foreground">
                {video.description}
              </p>
              <div className="flex gap-2 mt-4">
                <Button onClick={handleApprove}>Approve</Button>
                <Button variant="outline" onClick={() => onEdit(video.id)}>
                  Edit
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  );
}

// ❌ INCORRECT — implicit any, no types, messy
function VideoCard(props) {
  const [expanded, setExpanded] = useState(false)
  return <div>{props.video.title}</div>
}
```

### 3.3 Custom Hooks

```tsx
// ✅ CORRECT — Typed custom hook with error handling
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Video, VideoStatus } from "@/lib/types";

interface UseVideosOptions {
  channelId?: number;
  status?: VideoStatus;
  limit?: number;
}

export function useVideos(options: UseVideosOptions = {}) {
  const { channelId, status, limit = 50 } = options;
  
  return useQuery({
    queryKey: ["videos", { channelId, status, limit }],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (channelId) params.append("channel_id", String(channelId));
      if (status) params.append("status", status);
      params.append("limit", String(limit));
      
      const response = await api.get<Video[]>(`/videos?${params}`);
      return response.data;
    },
    staleTime: 30 * 1000,  // 30 seconds
  });
}

export function useApproveVideo() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (videoId: number) => {
      const response = await api.post(`/videos/${videoId}/approve`);
      return response.data;
    },
    onSuccess: (_, videoId) => {
      // Invalidate and refetch
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      queryClient.invalidateQueries({ queryKey: ["queue"] });
    },
  });
}
```

### 3.4 Zustand Store Patterns

```tsx
// ✅ CORRECT — Zustand store with TypeScript
import { create } from "zustand";
import { devtools } from "zustand/middleware";
import type { Channel } from "@/lib/types";

interface ChannelState {
  // State
  channels: Channel[];
  selectedChannelId: number | null;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  setChannels: (channels: Channel[]) => void;
  selectChannel: (id: number | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  
  // Computed (use selectors in components)
  getSelectedChannel: () => Channel | null;
}

export const useChannelStore = create<ChannelState>()(
  devtools(
    (set, get) => ({
      channels: [],
      selectedChannelId: null,
      isLoading: false,
      error: null,
      
      setChannels: (channels) => set({ channels }),
      selectChannel: (id) => set({ selectedChannelId: id }),
      setLoading: (isLoading) => set({ isLoading }),
      setError: (error) => set({ error }),
      
      getSelectedChannel: () => {
        const { channels, selectedChannelId } = get();
        return channels.find((c) => c.id === selectedChannelId) || null;
      },
    }),
    { name: "channel-store" }
  )
);

// Selector usage in component (prevents unnecessary re-renders)
const selectedChannel = useChannelStore(
  (state) => state.channels.find((c) => c.id === state.selectedChannelId)
);
```

---

## 4. Docker Standards

### 4.1 Dockerfile Best Practices

```dockerfile
# ✅ CORRECT — Multi-stage, non-root, layer caching

# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libmariadb-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Create non-root user
RUN groupadd -r ytagent && useradd -r -g ytagent ytagent

WORKDIR /app

# Copy only installed packages from builder
COPY --from=builder /root/.local /home/ytagent/.local
ENV PATH=/home/ytagent/.local/bin:$PATH

# Copy application code
COPY --chown=ytagent:ytagent ./app .

# Switch to non-root user
USER ytagent

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 4.2 Docker Compose Standards

```yaml
# ✅ CORRECT — Health checks, restart policies, resource limits
services:
  api:
    build:
      context: ./app
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    volumes:
      - /mnt/omv:/mnt/omv:ro
    ports:
      - "8000:8000"
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

---

## 5. Testing Standards

### 5.1 Python Tests (pytest)

```python
# tests/unit/services/test_channel_service.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.channel_service import ChannelService
from app.models.channel import Channel
from app.core.exceptions import NotFoundError


@pytest.fixture
def mock_db():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def channel_service(mock_db):
    return ChannelService(mock_db)


class TestChannelService:
    """Test suite for ChannelService."""
    
    async def test_get_channel_exists(self, channel_service, mock_db):
        """Should return channel when it exists."""
        # Arrange
        expected_channel = Channel(id=1, name="Test Channel", genre="lofi")
        mock_db.get.return_value = expected_channel
        
        # Act
        result = await channel_service.get(1)
        
        # Assert
        assert result == expected_channel
        mock_db.get.assert_called_once_with(Channel, 1)
    
    async def test_get_channel_not_found(self, channel_service, mock_db):
        """Should raise NotFoundError when channel doesn't exist."""
        # Arrange
        mock_db.get.return_value = None
        
        # Act & Assert
        with pytest.raises(NotFoundError, match="Channel 999 not found"):
            await channel_service.get(999)
    
    async def test_list_active_channels(self, channel_service, mock_db):
        """Should return only active channels."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            Channel(id=1, name="Active", is_active=True),
            Channel(id=2, name="Also Active", is_active=True),
        ]
        mock_db.execute.return_value = mock_result
        
        # Act
        result = await channel_service.list_active()
        
        # Assert
        assert len(result) == 2
        assert all(c.is_active for c in result)
```

### 5.2 Test Organization

```
tests/
├── conftest.py              # Shared fixtures
├── pytest.ini              # Configuration
├── unit/                   # Unit tests (no external deps)
│   ├── services/           # Service layer tests
│   ├── utils/              # Utility tests
│   └── models/             # Model tests
├── integration/            # Integration tests (with DB)
│   ├── test_api.py         # API endpoint tests
│   ├── test_database.py    # Database tests
│   └── test_celery.py      # Celery task tests
└── fixtures/               # Test data fixtures
    ├── channels.json
    └── videos.json
```

### 5.3 Frontend Tests (Future)

```tsx
// Component test pattern (Vitest + React Testing Library)
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { VideoCard } from "@/components/video/VideoCard";
import type { Video } from "@/lib/types";

const mockVideo: Video = {
  id: 1,
  currentTitle: "Test Video",
  status: "staging",
  thumbnailUrl: "/test.jpg",
  // ...
};

describe("VideoCard", () => {
  it("renders video title and status", () => {
    render(
      <VideoCard 
        video={mockVideo} 
        onApprove={vi.fn()} 
        onEdit={vi.fn()} 
      />
    );
    
    expect(screen.getByText("Test Video")).toBeInTheDocument();
    expect(screen.getByText("STAGING")).toBeInTheDocument();
  });
  
  it("calls onApprove when approve button clicked", () => {
    const onApprove = vi.fn();
    render(
      <VideoCard 
        video={mockVideo} 
        onApprove={onApprove} 
        onEdit={vi.fn()} 
      />
    );
    
    fireEvent.click(screen.getByText("Approve"));
    expect(onApprove).toHaveBeenCalledWith(1);
  });
});
```

---

## 6. Git Workflow

### 6.1 Branch Naming

```
feature/video-card-component
feature/telegram-integration
bugfix/queue-stuck-issue
hotfix/copyright-pause
refactor/analytics-service
docs/api-documentation
```

### 6.2 Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting (no code change)
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(upload): add retry logic with exponential backoff

Implement automatic retry for failed YouTube uploads.
Max 5 attempts with backoff: 5min, 10min, 20min, 40min, 60min.

Closes #42
---
fix(watcher): prevent processing incomplete files

Add file size stability check (5 seconds) before processing.
This prevents corruption from files still being copied.
---
docs(api): add OpenAPI documentation for video endpoints

Document all /videos endpoints with request/response schemas.
```

### 6.3 Pull Request Template

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] No hardcoded secrets
- [ ] Error handling implemented
- [ ] Logging added
```

---

## 7. Environment & Tooling

### 7.1 Required Tools

| Tool | Purpose | Version |
|------|---------|---------|
| Python | Backend runtime | 3.11+ |
| Node.js | Frontend runtime | 20+ |
| Docker | Containerization | 24+ |
| Docker Compose | Orchestration | 2.20+ |
| Ruff | Python linting/formatting | latest |
| pytest | Python testing | latest |
| Vitest | Frontend testing | latest |
| Prettier | TS/JS formatting | latest |

### 7.2 VS Code Extensions (Recommended)

| Extension | Purpose |
|-----------|---------|
| Python (Microsoft) | Python support |
| Ruff | Linting & formatting |
| Pylance | Type checking |
| ES7+ React/Redux | React snippets |
| Tailwind CSS IntelliSense | Tailwind support |
| Prettier | Code formatting |
| Docker | Docker support |
| Thunder Client | API testing |
| GitLens | Git visualization |

### 7.3 Pre-Commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
  
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest tests/unit -q
        language: system
        types: [python]
        pass_filenames: false
        always_run: true
```

---

## 8. Security Guidelines

### 8.1 Credential Handling

```python
# ✅ CORRECT — Environment variables only
from app.core.config import settings

api_key = settings.telegram_bot_token  # Loaded from .env

# ❌ INCORRECT — never hardcode
api_key = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
```

### 8.2 Input Validation

```python
# ✅ CORRECT — Validate all inputs
from pydantic import BaseModel, Field, validator

class VideoCreateRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=256)
    channel_id: int = Field(..., ge=1)
    file_size: int = Field(..., ge=0)
    
    @validator("filename")
    def validate_extension(cls, v: str) -> str:
        allowed = {".mp4", ".mov", ".avi"}
        if not any(v.lower().endswith(ext) for ext in allowed):
            raise ValueError(f"Invalid file extension. Allowed: {allowed}")
        return v

# ❌ INCORRECT — no validation
def create_video(filename, channel_id):
    # Directly uses inputs without validation
    pass
```

### 8.3 SQL Injection Prevention

```python
# ✅ CORRECT — Use SQLAlchemy ORM (parameterized queries)
result = await db.execute(
    select(Video).where(Video.channel_id == channel_id)
)

# ❌ INCORRECT — never use string formatting for SQL
query = f"SELECT * FROM videos WHERE channel_id = {channel_id}"  # DANGEROUS!
```

### 8.4 CORS Configuration

```python
# ✅ CORRECT — Restrict CORS to known origins
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://dashboard.local"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# ❌ INCORRECT — allow all origins
allow_origins=["*"]  # Only for development!
```
