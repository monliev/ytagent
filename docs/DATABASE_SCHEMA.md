# DATABASE_SCHEMA.md

## YTAgent — Database Schema Design

> **Version:** 1.0.0
> **Date:** 2025-06-26
> **Database:** MySQL 8.0
> **ORM:** SQLAlchemy 2.0 (async)

---

## 1. Schema Overview

### 1.1 Entity Relationship Diagram (High-Level)

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│    users    │       │   channels  │       │  gcp_projects│
│─────────────│       │─────────────│       │─────────────│
│ id (PK)     │       │ id (PK)     │◄──────│ channel_id  │
│ telegram_id │       │ name        │       │ project_id  │
│ role        │       │ genre       │       │ quota_limit │
│ created_at  │       │ folder_path │       │ quota_used  │
└─────────────┘       │ pref_time   │       │ status      │
                      │ is_active   │       └─────────────┘
                      │ auto_approve│
                      │ presets (JSON)       ┌─────────────┐
                      └─────────────┘       │  queue_tasks │
                             │              │─────────────│
                             │    ┌────────►│ id (PK)     │
                             │    │         │ video_id    │
                      ┌──────┴────┴───┐    │ channel_id  │
                      │     videos     │    │ priority    │
                      │───────────────│    │ status      │
                      │ id (PK)        │    │ scheduled_at│
                      │ channel_id (FK)│    │ retry_count │
                      │ filename       │    │ error_msg   │
                      │ file_path      │    └─────────────┘
                      │ file_size      │
                      │ duration       │       ┌─────────────┐
                      │ screenshot_path│       │analytics_   │
                      │ status         │◄─────│records      │
                      │ youtube_id     │       │─────────────│
                      │ scheduled_time │       │ id (PK)     │
                      │ uploaded_at    │       │ video_id    │
                      │ created_at     │       │ channel_id  │
                      └───────┬───────┘       │ views_24h   │
                              │               │ views_72h   │
              ┌───────────────┼───────────┐   │ ctr         │
              │               │           │   │ avd_seconds │
      ┌───────┴──────┐ ┌─────┴─────┐ ┌──┴───┴─┐ likes     │
      │thumbnail_    │ │metadata_  │ │system_ │ comments  │
      │drafts        │ │drafts     │ │logs    │ recorded_at│
      │──────────────│ │───────────│ │───────│└─────────────┘
      │ id (PK)      │ │ id (PK)   │ │id (PK)│
      │ video_id (FK)│ │video_id   │ │level  │
      │ image_path   │ │version_no │ │service│
      │ style        │ │title      │ │message│
      │ prompt       │ │description│ │details│
      │ confidence   │ │tags (JSON)│ │created│
      │ is_selected  │ │confidence │ └───────┘
      └──────────────┘ │is_approved│
                       └───────────┘
```

### 1.2 Schema Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Normalized Core** | Users, Channels, Videos are fully normalized |
| **JSON Flexibility** | Presets, drafts, tags use MySQL 8 JSON columns |
| **Soft Deletes** | `is_active` flags; no hard deletes for audit |
| **Temporal Data** | `created_at`, `updated_at`, `uploaded_at` on all entities |
| **Audit Logging** | `system_logs` table captures all significant events |
| **Indexing Strategy** | Indexes on FK columns, status fields, and timestamp ranges |

---

## 2. Table Definitions

### 2.1 Table: `users`

Supervisor and Editor accounts.

```sql
CREATE TABLE users (
    id              BIGINT UNSIGNED     AUTO_INCREMENT PRIMARY KEY,
    telegram_id     BIGINT UNSIGNED     NOT NULL UNIQUE COMMENT 'Telegram user ID for notifications',
    username        VARCHAR(64)         COMMENT 'Optional username',
    full_name       VARCHAR(128)        NOT NULL COMMENT 'Display name',
    role            ENUM('editor', 'supervisor', 'admin') NOT NULL DEFAULT 'supervisor',
    is_active       BOOLEAN             NOT NULL DEFAULT TRUE,
    notification_prefs JSON             COMMENT '{reports: true, alerts: true, approvals: true}',
    created_at      TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_telegram_id (telegram_id),
    INDEX idx_role (role),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='System users (Editor + Supervisor)';
```

**Initial Data:**

| id | telegram_id | full_name | role |
|----|-------------|-----------|------|
| 1 | `<supervisor_tg_id>` | Supervisor | supervisor |
| 2 | `<editor_tg_id>` | Editor | editor |

---

### 2.2 Table: `channels`

YouTube channel configuration and presets.

```sql
CREATE TABLE channels (
    id                  BIGINT UNSIGNED     AUTO_INCREMENT PRIMARY KEY,
    name                VARCHAR(128)        NOT NULL COMMENT 'Channel display name',
    genre               VARCHAR(64)         NOT NULL COMMENT 'Music genre (lofi, jazz, ambient, etc.)',
    folder_path         VARCHAR(256)        NOT NULL COMMENT 'OMV folder path, e.g., /mnt/omv/lofi_chill',
    preferred_time      TIME                NOT NULL DEFAULT '10:00:00' COMMENT 'Preferred upload time (WIB)',
    is_active           BOOLEAN             NOT NULL DEFAULT TRUE,
    auto_approve        BOOLEAN             NOT NULL DEFAULT FALSE COMMENT 'Auto-approve uploads for this channel',
    made_for_kids       BOOLEAN             NOT NULL DEFAULT FALSE COMMENT 'COPPA setting',
    
    -- Presets (JSON for flexibility)
    preset_title_template   VARCHAR(256)    COMMENT 'e.g., "{mood} Lofi Beats for {activity}"',
    preset_description_template TEXT        COMMENT 'Template with placeholders',
    preset_tags             JSON            COMMENT 'Default tags array',
    preset_social_links     JSON            COMMENT '{instagram: "...", spotify: "..."}',
    
    -- Thumbnail preset
    thumbnail_style_name    VARCHAR(64)     COMMENT 'e.g., "lofi-retro"',
    thumbnail_style_prompt  TEXT            COMMENT 'AI prompt for thumbnail generation',
    -- NULL = not yet confirmed by Supervisor; NOT NULL = confirmed at this datetime
    -- Use this instead of a boolean flag so it can be reset and is self-auditing.
    thumbnail_style_confirmed_at TIMESTAMP  NULL DEFAULT NULL
                                            COMMENT 'When Supervisor first confirmed a thumbnail style. NULL = first-time style selection still needed.',
    
    -- GCP credentials reference (actual credentials in channel_credentials table)
    gcp_project_id          VARCHAR(128)    COMMENT 'Active Google Cloud project identifier',
    
    -- Timestamps
    created_at              TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_genre (genre),
    INDEX idx_is_active (is_active),
    INDEX idx_folder_path (folder_path),
    INDEX idx_auto_approve (auto_approve),
    FULLTEXT INDEX ft_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='YouTube channel configurations and presets';
```

**Design Note — `thumbnail_style_confirmed_at`:**
- Replaces the previous `thumbnail_first_time BOOLEAN DEFAULT TRUE` flag.
- `NULL` → Supervisor has not yet selected a style; show the 3-option picker.
- `NOT NULL` → Style already confirmed; auto-use `thumbnail_style_name`.
- Can be reset to `NULL` anytime via dashboard to force Supervisor to re-pick a style.
- Self-auditing: records when the style was confirmed, unlike a boolean.

```sql
-- Check if first-time selection is needed
SELECT thumbnail_style_confirmed_at IS NULL AS needs_style_selection FROM channels WHERE id = ?;

-- Confirm a style
UPDATE channels SET 
    thumbnail_style_name = 'lofi-retro',
    thumbnail_style_prompt = '...prompt...',
    thumbnail_style_confirmed_at = NOW()
WHERE id = ?;

-- Reset to force re-selection
UPDATE channels SET thumbnail_style_confirmed_at = NULL WHERE id = ?;
```

**Sample Data:**

| id | name | genre | folder_path | preferred_time | thumbnail_style_name | thumbnail_style_prompt |
|----|------|-------|-------------|----------------|---------------------|----------------------|
| 1 | Lofi Chill | lofi | /mnt/omv/lofi_chill | 10:00:00 | lofi-retro | "High-contrast, retro typography, muted cool tones, grain texture, minimalist composition, lofi aesthetic" |
| 2 | Oud Fusion Jazz | jazz | /mnt/omv/oud_jazz | 14:00:00 | jazz-arabic | "Warm earthy palette, elegant Arabic calligraphy, golden accents, sophisticated jazz atmosphere, rich textures" |

---

### 2.3 Table: `channel_credentials`

OAuth credentials isolated from the channels table for security. Each channel can have multiple credential records (one per GCP project). Active credential is identified via `gcp_projects` table.

> **Security Rationale:** Storing encrypted OAuth tokens in a separate table with more restrictive access patterns limits blast radius if a channels record is ever read without authorization. Each channel's credentials are encrypted with a **different derived key** (base key + channel_id salt via HKDF), so compromising one channel's encryption does not expose all others.

```sql
CREATE TABLE channel_credentials (
    id                  BIGINT UNSIGNED     AUTO_INCREMENT PRIMARY KEY,
    channel_id          BIGINT UNSIGNED     NOT NULL,
    gcp_project_id      VARCHAR(128)        NOT NULL COMMENT 'GCP project this credential belongs to',
    
    -- Encrypted credentials (AES-256 Fernet, key derived per channel)
    oauth_credentials_encrypted TEXT        NOT NULL COMMENT 'Encrypted JSON credentials blob',
    oauth_refresh_token_encrypted TEXT      NOT NULL COMMENT 'Encrypted refresh token',
    oauth_token_expiry  TIMESTAMP           COMMENT 'Token expiration time (unencrypted for scheduling)',
    
    -- Status
    is_active           BOOLEAN             NOT NULL DEFAULT TRUE COMMENT 'Active credential for this channel+project',
    last_refreshed_at   TIMESTAMP           COMMENT 'When token was last refreshed',
    last_error          TEXT                COMMENT 'Last refresh error if any',
    
    -- Encryption metadata
    key_version         TINYINT UNSIGNED    NOT NULL DEFAULT 1 COMMENT 'Key version for rotation support',
    
    -- Timestamps
    created_at          TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
    INDEX idx_channel_project (channel_id, gcp_project_id),
    INDEX idx_is_active (is_active),
    INDEX idx_token_expiry (oauth_token_expiry)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='OAuth credentials isolated per channel for security';
```

**Access Pattern:**
```python
# Load credentials for upload
creds = db.execute(
    select(ChannelCredentials)
    .where(ChannelCredentials.channel_id == channel_id)
    .where(ChannelCredentials.gcp_project_id == active_project_id)
    .where(ChannelCredentials.is_active == True)
).scalar_one()
```

---

### 2.4 (was 2.3) Table: `gcp_projects`

Quota tracking per GCP project.

```sql
CREATE TABLE gcp_projects (
    id              BIGINT UNSIGNED     AUTO_INCREMENT PRIMARY KEY,
    channel_id      BIGINT UNSIGNED     NOT NULL,
    project_name    VARCHAR(128)        NOT NULL COMMENT 'GCP project name',
    project_id      VARCHAR(128)        NOT NULL UNIQUE COMMENT 'GCP project ID',
    client_secret_path VARCHAR(256)     NOT NULL COMMENT 'Path to client_secret.json',
    quota_limit     INT UNSIGNED        NOT NULL DEFAULT 10000 COMMENT 'Daily quota limit (units)',
    quota_used      INT UNSIGNED        NOT NULL DEFAULT 0 COMMENT 'Units used today',
    last_reset      DATE                NOT NULL DEFAULT (CURRENT_DATE) COMMENT 'Last quota reset date',
    status          ENUM('active', 'suspended', 'quota_exceeded') NOT NULL DEFAULT 'active',
    created_at      TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
    INDEX idx_channel_id (channel_id),
    INDEX idx_project_id (project_id),
    INDEX idx_status (status),
    INDEX idx_last_reset (last_reset)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='GCP project quota management per channel';
```

---

### 2.4 Table: `videos`

Central entity for video lifecycle management.

```sql
CREATE TABLE videos (
    id              BIGINT UNSIGNED     AUTO_INCREMENT PRIMARY KEY,
    channel_id      BIGINT UNSIGNED     NOT NULL,
    
    -- File info
    filename        VARCHAR(256)        NOT NULL COMMENT 'Original filename',
    file_path       VARCHAR(512)        NOT NULL COMMENT 'Full path on OMV',
    file_size_bytes BIGINT UNSIGNED     NOT NULL COMMENT 'File size in bytes',
    duration_seconds INT UNSIGNED       COMMENT 'Video duration from ffprobe',
    resolution      VARCHAR(16)         COMMENT 'e.g., 1920x1080',
    
    -- Screenshot
    screenshot_path VARCHAR(512)        COMMENT 'Path to frame30 screenshot',
    
    -- Lifecycle status
    status          ENUM(
                        'detected',     -- File detected, not yet processed
                        'preparing',    -- Screenshot + AI generation in progress
                        'staging',      -- Ready for Supervisor approval
                        'approved',     -- Approved, waiting in queue
                        'queued',       -- In upload queue
                        'uploading',    -- Currently uploading
                        'uploaded',     -- Successfully uploaded
                        'failed',       -- Upload failed (retries exhausted)
                        'discarded',    -- Supervisor discarded
                        'error'         -- Processing error
                    ) NOT NULL DEFAULT 'detected',
    
    -- YouTube
    youtube_video_id    VARCHAR(32)     COMMENT 'YouTube video ID after upload',
    youtube_privacy     ENUM('private', 'public', 'unlisted') DEFAULT 'private',
    
    -- Scheduling
    scheduled_time      TIMESTAMP       COMMENT 'Planned upload time (override)',
    uploaded_at         TIMESTAMP       COMMENT 'Actual upload completion time',
    
    -- Retry tracking
    retry_count         INT UNSIGNED    NOT NULL DEFAULT 0,
    last_error          TEXT            COMMENT 'Last error message',
    
    -- Metadata ( denormalized for quick access )
    current_title       VARCHAR(100)    COMMENT 'Final/approved title',
    current_description TEXT            COMMENT 'Final/approved description',
    current_tags        JSON            COMMENT 'Final/approved tags array',
    
    -- Flags
    is_favorite         BOOLEAN         NOT NULL DEFAULT FALSE COMMENT 'Supervisor marked as favorite',
    notes               TEXT            COMMENT 'Supervisor notes',
    
    -- Timestamps
    created_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Constraints & Indexes
    FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
    INDEX idx_channel_id (channel_id),
    INDEX idx_status (status),
    INDEX idx_youtube_id (youtube_video_id),
    INDEX idx_scheduled_time (scheduled_time),
    INDEX idx_created_at (created_at),
    INDEX idx_status_channel (status, channel_id),
    INDEX idx_staging_lookup (status, channel_id, created_at) 
        COMMENT 'Fast lookup for staging area',
    FULLTEXT INDEX ft_title (current_title)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Video lifecycle from detection to upload';
```

**Status Lifecycle:**

```
detected ──► preparing ──► staging ──► approved ──► queued ──► uploading ──► uploaded
    │            │            │            │
    ▼            ▼            ▼            ▼
  error       error      discarded     failed
                                          │
                                          ▼
                                       (retry x5)
                                          │
                                          ▼
                                        failed (permanent)
```

---

### 2.5 Table: `thumbnail_drafts`

AI-generated thumbnail options per video.

```sql
CREATE TABLE thumbnail_drafts (
    id              BIGINT UNSIGNED     AUTO_INCREMENT PRIMARY KEY,
    video_id        BIGINT UNSIGNED     NOT NULL,
    
    -- Image info
    image_path      VARCHAR(512)        NOT NULL COMMENT 'Path to generated thumbnail',
    
    -- Generation metadata
    style_name      VARCHAR(64)         NOT NULL COMMENT 'e.g., "lofi-retro"',
    prompt_used     TEXT                NOT NULL COMMENT 'Full AI prompt used',
    
    -- Quality metrics
    confidence_score DECIMAL(5,2)       COMMENT '0.00 - 100.00',
    
    -- Selection
    is_selected     BOOLEAN             NOT NULL DEFAULT FALSE COMMENT 'Supervisor selected this one',
    selection_reason VARCHAR(256)       COMMENT 'Why this was selected',
    
    -- Timestamps
    created_at      TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    INDEX idx_video_id (video_id),
    INDEX idx_is_selected (is_selected),
    INDEX idx_style_name (style_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='AI-generated thumbnail options';
```

---

### 2.6 Table: `metadata_drafts`

AI-generated metadata versions per video.

```sql
CREATE TABLE metadata_drafts (
    id              BIGINT UNSIGNED     AUTO_INCREMENT PRIMARY KEY,
    video_id        BIGINT UNSIGNED     NOT NULL,
    
    -- Versioning
    version_number  INT UNSIGNED        NOT NULL DEFAULT 1 COMMENT 'Increment on each generation',
    generation_type ENUM('auto', 'manual_edit', 'ai_suggestion') NOT NULL DEFAULT 'auto',
    
    -- Content
    title           VARCHAR(100)        NOT NULL COMMENT 'Generated title',
    description     TEXT                NOT NULL COMMENT 'Generated description',
    tags            JSON                NOT NULL COMMENT 'Array of tag strings',
    language        VARCHAR(8)          NOT NULL DEFAULT 'en' COMMENT 'ISO language code',
    tone            VARCHAR(32)         COMMENT 'e.g., relaxed, energetic, sophisticated',
    
    -- Quality
    confidence_score DECIMAL(5,2)       NOT NULL COMMENT '0.00 - 100.00',
    quality_score    INT UNSIGNED       COMMENT 'AI quality rating 1-10',
    
    -- Approval
    is_approved     BOOLEAN             NOT NULL DEFAULT FALSE,
    approved_by     BIGINT UNSIGNED     COMMENT 'user_id who approved',
    approved_at     TIMESTAMP,
    
    -- Feedback
    supervisor_feedback TEXT            COMMENT 'Feedback from Supervisor',
    
    -- A/B Testing
    ab_test_group   ENUM('control', 'variant_a', 'variant_b') DEFAULT 'control',
    
    -- Timestamps
    created_at      TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    FOREIGN KEY (approved_by) REFERENCES users(id),
    INDEX idx_video_id (video_id),
    INDEX idx_version (video_id, version_number),
    INDEX idx_is_approved (is_approved),
    INDEX idx_ab_test (ab_test_group),
    FULLTEXT INDEX ft_title (title),
    FULLTEXT INDEX ft_description (description)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='AI-generated metadata with versioning';
```

---

### 2.7 Table: `queue_tasks`

Upload queue management.

```sql
CREATE TABLE queue_tasks (
    id              BIGINT UNSIGNED     AUTO_INCREMENT PRIMARY KEY,
    video_id        BIGINT UNSIGNED     NOT NULL UNIQUE COMMENT 'One task per video',
    channel_id      BIGINT UNSIGNED     NOT NULL,
    
    -- Priority & scheduling
    priority        INT                 NOT NULL DEFAULT 0 COMMENT 'Higher = earlier (override)',
    scheduled_at    TIMESTAMP           NOT NULL COMMENT 'When this task should run',
    
    -- Status
    status          ENUM(
                        'pending',      -- Waiting in queue
                        'processing',   -- Currently being uploaded
                        'completed',    -- Upload successful
                        'failed',       -- Failed (retries may apply)
                        'cancelled'     -- Cancelled by Supervisor
                    ) NOT NULL DEFAULT 'pending',
    
    -- Execution tracking
    started_at      TIMESTAMP           COMMENT 'When worker picked up this task',
    completed_at    TIMESTAMP           COMMENT 'When upload finished',
    worker_id       VARCHAR(64)         COMMENT 'Celery worker identifier',
    
    -- Retry
    retry_count     INT UNSIGNED        NOT NULL DEFAULT 0,
    max_retries     INT UNSIGNED        NOT NULL DEFAULT 5,
    next_retry_at   TIMESTAMP           COMMENT 'Next retry attempt time',
    error_message   TEXT                COMMENT 'Last error details',
    
    -- Celery integration
    celery_task_id  VARCHAR(128)        COMMENT 'Celery task UUID',
    
    -- Timestamps
    created_at      TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
    INDEX idx_channel_id (channel_id),
    INDEX idx_status (status),
    INDEX idx_scheduled_at (scheduled_at),
    INDEX idx_status_priority (status, priority, scheduled_at)
        COMMENT 'Primary queue ordering index',
    INDEX idx_celery_task (celery_task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Sequential upload queue';
```

**Queue Ordering Logic:**

```sql
-- Tasks are picked up in this order:
SELECT * FROM queue_tasks 
WHERE status = 'pending' 
  AND scheduled_at <= NOW()
ORDER BY priority DESC, scheduled_at ASC, created_at ASC
LIMIT 1;
```

---

### 2.8 Table: `analytics_records`

Performance metrics per video.

```sql
CREATE TABLE analytics_records (
    id              BIGINT UNSIGNED     AUTO_INCREMENT PRIMARY KEY,
    video_id        BIGINT UNSIGNED     NOT NULL,
    channel_id      BIGINT UNSIGNED     NOT NULL,
    youtube_video_id VARCHAR(32)        NOT NULL,
    
    -- Time-based metrics
    recorded_at     TIMESTAMP           NOT NULL COMMENT 'When this snapshot was taken',
    hours_since_publish INT UNSIGNED    NOT NULL COMMENT 'Hours since video was published',
    
    -- View metrics
    views           BIGINT UNSIGNED     NOT NULL DEFAULT 0,
    views_gained    BIGINT UNSIGNED     COMMENT 'Views gained since last record',
    
    -- Engagement
    likes           BIGINT UNSIGNED     DEFAULT 0,
    dislikes        BIGINT UNSIGNED     DEFAULT 0 COMMENT 'If available via API',
    comments        BIGINT UNSIGNED     DEFAULT 0,
    shares          BIGINT UNSIGNED     DEFAULT 0,
    
    -- Performance ratios
    ctr             DECIMAL(5,2)        COMMENT 'Click-through rate %',
    avd_seconds     INT UNSIGNED        COMMENT 'Average view duration in seconds',
    avd_percentage  DECIMAL(5,2)        COMMENT 'AVD as % of total duration',
    
    -- Traffic sources (JSON for flexibility)
    traffic_sources JSON                COMMENT '{browse: 45%, suggested: 30%, search: 15%, ...}',
    
    -- Demographics (JSON)
    demographics    JSON                COMMENT '{age_ranges: {...}, countries: {...}}',
    
    -- Raw YouTube response (for debugging)
    raw_data        JSON,
    
    -- Timestamps
    created_at      TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
    INDEX idx_video_id (video_id),
    INDEX idx_channel_id (channel_id),
    INDEX idx_youtube_id (youtube_video_id),
    INDEX idx_recorded_at (recorded_at),
    INDEX idx_hours_since (hours_since_publish),
    INDEX idx_channel_recorded (channel_id, recorded_at)
        COMMENT 'Fast analytics queries per channel',
    INDEX idx_ctr (ctr),
    INDEX idx_avd (avd_seconds)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Video performance analytics snapshots';
```

---

### 2.9 Table: `performance_insights`

AI-generated insights and alerts.

```sql
CREATE TABLE performance_insights (
    id              BIGINT UNSIGNED     AUTO_INCREMENT PRIMARY KEY,
    channel_id      BIGINT UNSIGNED     NOT NULL,
    video_id        BIGINT UNSIGNED     COMMENT 'Nullable: global channel insight',
    
    -- Classification
    insight_type    ENUM(
                        'anomaly',      -- Something is wrong
                        'suggestion',   -- Improvement recommendation
                        'ab_test_result', -- A/B test outcome
                        'trend',        -- Pattern detected
                        'milestone'     -- Achievement (100 views, etc.)
                    ) NOT NULL,
    
    -- Content
    title           VARCHAR(256)        NOT NULL COMMENT 'Short insight title',
    message         TEXT                NOT NULL COMMENT 'Full insight message',
    severity        ENUM('info', 'warning', 'critical') NOT NULL DEFAULT 'info',
    
    -- Metrics referenced
    metric_type     VARCHAR(32)         COMMENT 'ctr, avd, views, etc.',
    metric_value    DECIMAL(10,2)       COMMENT 'The actual value',
    metric_average  DECIMAL(10,2)       COMMENT 'Channel average for comparison',
    
    -- Action
    suggested_action TEXT               COMMENT 'What to do about this',
    is_actionable   BOOLEAN             NOT NULL DEFAULT TRUE COMMENT 'Does this require action?',
    
    -- Status
    is_read         BOOLEAN             NOT NULL DEFAULT FALSE,
    read_at         TIMESTAMP,
    dismissed       BOOLEAN             NOT NULL DEFAULT FALSE,
    
    -- Notification
    sent_to_telegram BOOLEAN            NOT NULL DEFAULT FALSE,
    telegram_message_id BIGINT UNSIGNED  COMMENT 'Reference to sent message',
    
    -- Timestamps
    created_at      TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    INDEX idx_channel_id (channel_id),
    INDEX idx_video_id (video_id),
    INDEX idx_insight_type (insight_type),
    INDEX idx_severity (severity),
    INDEX idx_is_read (is_read),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='AI-generated performance insights and alerts';
```

---

### 2.10 Table: `system_logs`

Structured logging for debugging and audit.

```sql
CREATE TABLE system_logs (
    id              BIGINT UNSIGNED     AUTO_INCREMENT PRIMARY KEY,
    
    -- Classification
    level           ENUM('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL') NOT NULL,
    service         VARCHAR(64)         NOT NULL COMMENT 'Which service generated this',
    event_type      VARCHAR(64)         NOT NULL COMMENT 'e.g., video_detected, upload_started',
    
    -- Context
    video_id        BIGINT UNSIGNED     COMMENT 'Related video (if applicable)',
    channel_id      BIGINT UNSIGNED     COMMENT 'Related channel (if applicable)',
    user_id         BIGINT UNSIGNED     COMMENT 'Acting user (if applicable)',
    
    -- Content
    message         TEXT                NOT NULL,
    details         JSON                COMMENT 'Structured additional data',
    
    -- Source
    source_ip       VARCHAR(45)         COMMENT 'IPv4/IPv6 address',
    request_id      VARCHAR(64)         COMMENT 'Trace/correlation ID',
    
    -- Timestamps
    created_at      TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_level (level),
    INDEX idx_service (service),
    INDEX idx_event_type (event_type),
    INDEX idx_video_id (video_id),
    INDEX idx_channel_id (channel_id),
    INDEX idx_created_at (created_at),
    INDEX idx_level_created (level, created_at)
        COMMENT 'Fast error log queries',
    INDEX idx_request_id (request_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Structured system logs for debugging and audit';
```

---

### 2.11 Table: `notification_history`

Track all sent notifications for audit.

```sql
CREATE TABLE notification_history (
    id              BIGINT UNSIGNED     AUTO_INCREMENT PRIMARY KEY,
    user_id         BIGINT UNSIGNED     NOT NULL,
    
    -- Content
    notification_type ENUM(
                        'video_ready',      -- Video ready for approval
                        'upload_complete',  -- Upload finished
                        'upload_failed',    -- Upload failed permanently
                        'daily_report',     -- 08:00 report
                        'anomaly_alert',    -- Performance anomaly
                        'copyright_alert',  -- Copyright claim detected
                        'quota_warning',    -- GCP quota warning
                        'system_alert'      -- Other system alert
                    ) NOT NULL,
    
    title           VARCHAR(256)        NOT NULL,
    message         TEXT                NOT NULL,
    
    -- Delivery
    channel         ENUM('telegram', 'dashboard') NOT NULL DEFAULT 'telegram',
    status          ENUM('sent', 'delivered', 'read', 'failed') NOT NULL DEFAULT 'sent',
    external_id     VARCHAR(128)        COMMENT 'Telegram message ID or similar',
    
    -- Related entities
    video_id        BIGINT UNSIGNED,
    channel_id      BIGINT UNSIGNED,
    
    -- Timestamps
    sent_at         TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at         TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_notification_type (notification_type),
    INDEX idx_status (status),
    INDEX idx_sent_at (sent_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Notification delivery tracking';
```

---

## 3. Qdrant Collections Schema

### 3.1 Collection: `video_performance`

Stores performance vectors for pattern recognition.

```python
from qdrant_client.models import Distance, VectorParams, FieldCondition

collection_config = {
    "collection_name": "video_performance",
    "vectors_config": VectorParams(
        size=384,           # Sentence transformer embedding size
        distance=Distance.COSINE
    ),
    "optimizers_config": {
        "default_segment_number": 2
    }
}

# Point structure (payload)
point_payload = {
    "video_id": 123,
    "channel_id": 5,
    "title_text": "Relaxing Lofi Beats for Study",
    "genre": "lofi",
    "thumbnail_style": "lofi-retro",
    "title_template": "{mood} Lofi Beats for {activity}",
    "ctr": 3.2,
    "avd_seconds": 145,
    "views_24h": 250,
    "views_72h": 800,
    "likes": 45,
    "comments": 12,
    "publish_date": "2025-06-20",
    "performance_tier": "above_average"  # below_average, average, above_average, viral
}
```

### 3.2 Collection: `title_embeddings`

Stores title embeddings for similarity-based suggestions.

```python
collection_config = {
    "collection_name": "title_embeddings",
    "vectors_config": VectorParams(
        size=384,
        distance=Distance.COSINE
    )
}

point_payload = {
    "video_id": 123,
    "channel_id": 5,
    "title_text": "Relaxing Lofi Beats for Study",
    "performance_score": 85.5,  # Normalized 0-100
    "ctr": 3.2,
    "views_24h": 250
}
```

---

## 4. Indexes Summary

### 4.1 MySQL Indexes

| Table | Index Name | Columns | Purpose |
|-------|-----------|---------|---------|
| users | idx_telegram_id | telegram_id | Fast user lookup by Telegram ID |
| users | idx_role | role | Filter by role |
| channels | idx_genre | genre | Filter by genre |
| channels | idx_is_active | is_active | Filter active channels |
| channels | ft_name | name (FULLTEXT) | Search channels |
| videos | idx_channel_id | channel_id | Filter by channel |
| videos | idx_status | status | Filter by lifecycle status |
| videos | idx_status_channel | status, channel_id | Staging area query |
| videos | idx_staging_lookup | status, channel_id, created_at | Fast staging lookup |
| videos | ft_title | current_title (FULLTEXT) | Search videos |
| thumbnail_drafts | idx_video_id | video_id | Get drafts for video |
| metadata_drafts | idx_video_version | video_id, version_number | Version lookup |
| queue_tasks | idx_status_priority | status, priority, scheduled_at | Queue ordering |
| analytics_records | idx_channel_recorded | channel_id, recorded_at | Analytics queries |
| analytics_records | idx_ctr | ctr | Anomaly detection |
| performance_insights | idx_channel_unread | channel_id, is_read | Unread insights |
| system_logs | idx_level_created | level, created_at | Error log queries |

### 4.2 Qdrant Indexes

| Collection | Indexed Fields | Purpose |
|------------|---------------|---------|
| video_performance | channel_id, performance_tier, genre | Filtered similarity search |
| title_embeddings | channel_id, performance_score | Title recommendation |

---

## 5. Data Lifecycle

### 5.1 Video Lifecycle State Machine

```
[File Copied to OMV]
    │
    ▼
┌──────────┐     ┌──────────┐     ┌──────────┐
│ DETECTED │────►│ PREPARING│────►│ STAGING  │
│          │     │          │     │ (AI ready│
│ Watcher  │     │ ffmpeg   │     │ for      │
│ detects  │     │ + AI gen │     │ approval)│
└──────────┘     └──────────┘     └────┬─────┘
    │                                   │
    │ (error)                           │ Supervisor [Approve]
    ▼                                   ▼
┌──────────┐                      ┌──────────┐
│  ERROR   │                      │ APPROVED │
│          │                      │          │
│ Logged,  │                      │ Enters   │
│ notified │                      │ queue    │
└──────────┘                      └────┬─────┘
                                       │
                    Supervisor [Discard] │
                          │              │
                          ▼              ▼
                    ┌──────────┐   ┌──────────┐
                    │ DISCARDED│   │  QUEUED  │
                    │          │   │          │
                    │ Draft    │   │ Waiting  │
                    │ deleted  │   │ in line  │
                    └──────────┘   └────┬─────┘
                                          │
                                          ▼
                                    ┌──────────┐
                                    │ UPLOADING│
                                    │          │
                                    │ Active   │
                                    │ upload   │
                                    └────┬─────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
              ┌──────────┐        ┌──────────┐          ┌──────────┐
              │ UPLOADED │        │  FAILED  │          │  FAILED  │
              │          │        │ (retry)  │          │(permanent│
              │ Success! │        │          │          │          │
              │ Analytics│        │ Retry    │          │ Notify   │
              │ scheduled│        │ count++  │          │ Supervisor
              └──────────┘        └──────────┘          └──────────┘
```

### 5.2 Retention Policy

| Data Type | Retention | Action |
|-----------|-----------|--------|
| Video files (OMV) | Forever | Never delete (user requirement) |
| Thumbnail drafts | 90 days | Soft delete after 90 days |
| Metadata drafts | 90 days | Soft delete after 90 days |
| Analytics records | 2 years | Archive after 2 years |
| Performance insights | 1 year | Soft delete after 1 year |
| System logs | **30 days** | **Purge rows older than 30 days via weekly Celery task** |
| Notification history | 1 year | Soft delete after 1 year |
| Queue tasks (completed) | 30 days | Archive after 30 days |

**Log Rotation (System Logs):**

Without rotation, `system_logs` will grow to millions of rows quickly (30 channels, intensive logging). A weekly Celery Beat task handles rotation:

```python
# tasks/maintenance.py
@shared_task
def rotate_system_logs() -> dict:
    """Delete system_logs rows older than 30 days. Runs weekly (Sunday 02:00 WIB)."""
    cutoff = datetime.utcnow() - timedelta(days=30)
    with Session(engine) as db:
        deleted = db.execute(
            delete(SystemLog).where(SystemLog.created_at < cutoff)
        )
        db.commit()
    logger.info("log_rotation_complete", deleted_rows=deleted.rowcount)
    return {"deleted": deleted.rowcount}
```

**Celery Beat schedule entry:**
```python
"rotate-system-logs": {
    "task": "tasks.maintenance.rotate_system_logs",
    "schedule": crontab(hour="2", minute="0", day_of_week="0"),  # Sunday 02:00 WIB
},
```

**MySQL Table Partitioning (Optional, if log volume is very high):**
```sql
-- Partition system_logs by month for fast range deletes
ALTER TABLE system_logs
PARTITION BY RANGE (YEAR(created_at) * 100 + MONTH(created_at)) (
    PARTITION p202506 VALUES LESS THAN (202507),
    PARTITION p202507 VALUES LESS THAN (202508),
    -- Add partitions monthly via Celery task
    PARTITION p_future VALUES LESS THAN MAXVALUE
);
-- Drop old partition = O(1) operation instead of DELETE
ALTER TABLE system_logs DROP PARTITION p202506;
```

---

## 6. SQLAlchemy 2.0 Model Definitions

### 6.1 Base Configuration

```python
# app/models/base.py
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime

class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all models."""
    pass

class TimestampMixin:
    """Adds created_at and updated_at columns."""
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, 
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
```

### 6.2 Channel Model

```python
# app/models/channel.py
from sqlalchemy import String, Boolean, JSON, Text, Time, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional
from .base import Base, TimestampMixin

class Channel(Base, TimestampMixin):
    __tablename__ = "channels"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    genre: Mapped[str] = mapped_column(String(64), nullable=False)
    folder_path: Mapped[str] = mapped_column(String(256), nullable=False)
    preferred_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=False)
    made_for_kids: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Presets
    preset_title_template: Mapped[str | None] = mapped_column(String(256))
    preset_description_template: Mapped[str | None] = mapped_column(Text)
    preset_tags: Mapped[list | None] = mapped_column(JSON)
    preset_social_links: Mapped[dict | None] = mapped_column(JSON)
    
    # Thumbnail
    thumbnail_style_name: Mapped[str | None] = mapped_column(String(64))
    thumbnail_style_prompt: Mapped[str | None] = mapped_column(Text)
    # Replaces old thumbnail_first_time boolean.
    # None = style not yet confirmed; datetime = confirmed at that time.
    thumbnail_style_confirmed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, default=None)
    
    @property
    def needs_style_selection(self) -> bool:
        """True if Supervisor has not yet confirmed a thumbnail style."""
        return self.thumbnail_style_confirmed_at is None
    
    # GCP
    gcp_project_id: Mapped[str | None] = mapped_column(String(128))
    
    # Relationships
    videos: Mapped[list["Video"]] = relationship(back_populates="channel")
    gcp_projects: Mapped[list["GCPProject"]] = relationship(back_populates="channel")
    credentials: Mapped[list["ChannelCredentials"]] = relationship(back_populates="channel")
    queue_tasks: Mapped[list["QueueTask"]] = relationship(back_populates="channel")
```

### 6.3 Video Model

```python
# app/models/video.py
from sqlalchemy import String, Text, JSON, Enum, ForeignKey, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import Enum as PyEnum
from .base import Base, TimestampMixin

class VideoStatus(PyEnum):
    DETECTED = "detected"
    PREPARING = "preparing"
    STAGING = "staging"
    APPROVED = "approved"
    QUEUED = "queued"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    FAILED = "failed"
    DISCARDED = "discarded"
    ERROR = "error"

class Video(Base, TimestampMixin):
    __tablename__ = "videos"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), nullable=False)
    
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column()
    resolution: Mapped[str | None] = mapped_column(String(16))
    
    screenshot_path: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus), 
        default=VideoStatus.DETECTED,
        nullable=False
    )
    
    youtube_video_id: Mapped[str | None] = mapped_column(String(32))
    youtube_privacy: Mapped[str] = mapped_column(String(16), default="private")
    scheduled_time: Mapped[datetime | None] = mapped_column()
    uploaded_at: Mapped[datetime | None] = mapped_column()
    
    retry_count: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    
    current_title: Mapped[str | None] = mapped_column(String(100))
    current_description: Mapped[str | None] = mapped_column(Text)
    current_tags: Mapped[list | None] = mapped_column(JSON)
    
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    
    # Relationships
    channel: Mapped["Channel"] = relationship(back_populates="videos")
    thumbnail_drafts: Mapped[list["ThumbnailDraft"]] = relationship(back_populates="video")
    metadata_drafts: Mapped[list["MetadataDraft"]] = relationship(back_populates="video")
    queue_task: Mapped["QueueTask | None"] = relationship(back_populates="video")
    analytics: Mapped[list["AnalyticsRecord"]] = relationship(back_populates="video")
```

---

## 7. Migration Strategy

### 7.1 Tool: Alembic

Use Alembic (SQLAlchemy's migration tool) for all schema changes.

```bash
# Initialize Alembic
alembic init alembic

# Generate migration from models
alembic revision --autogenerate -m "Initial schema"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### 7.2 Migration Files

```
alembic/
├── versions/
│   ├── 001_initial_schema.py        # Base tables
│   ├── 002_add_queue_tasks.py       # Queue management
│   ├── 003_add_analytics.py         # Analytics tables
│   └── 004_add_insights.py          # Performance insights
├── env.py
├── script.py.mako
└── alembic.ini
```

### 7.3 Initial Data Migration

```python
# alembic/versions/001_initial_schema.py (excerpt)
def upgrade() -> None:
    # Create tables...
    
    # Insert default users
    op.execute("""
        INSERT INTO users (telegram_id, full_name, role, is_active) 
        VALUES 
            (123456789, 'Supervisor', 'supervisor', TRUE),
            (987654321, 'Editor', 'editor', TRUE)
    """)
```

---

## 8. Database Connection Configuration

### 8.1 Async Engine Setup

```python
# app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,           # SQL logging in debug mode
    pool_size=10,                  # Connection pool size
    max_overflow=20,               # Extra connections under load
    pool_pre_ping=True,            # Verify connection before use
    pool_recycle=3600,             # Recycle connections after 1 hour
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_db() -> AsyncSession:
    """Dependency for FastAPI routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

### 8.2 Configuration

```python
# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # MySQL (asyncmy driver)
    database_url: str = "mysql+asyncmy://ytagent:password@localhost:3306/ytagent"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    
    # Debug
    debug: bool = False
    
    class Config:
        env_file = ".env"
```
