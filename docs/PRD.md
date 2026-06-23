# PRD.md

## YTAgent — Product Requirements Document

> **Version:** 1.0.0
> **Date:** 2025-06-26
> **Status:** Final
> **Owner:** Nandito Monliev
> **Target Users:** Editor (Content Creator) + Supervisor (Channel Manager)

---

## 1. Overview

### 1.1 Product Vision

YTAgent is an AI-powered orchestrator that automates YouTube content management across 10–30 music channels. It transforms a labor-intensive, repetitive workflow into a supervisory experience where the human only approves pre-generated drafts while the AI handles detection, preparation, upload, analytics, and continuous improvement.

### 1.2 Problem Statement

**Current Pain Points:**

| Stakeholder | Pain Point | Impact |
|-------------|-----------|--------|
| **Editor (Husband)** | Renders high-volume content but must manage metadata, upload to 10–30 channels individually, and do manual evaluation | Creative energy drained by operational tasks |
| **Supervisor (Wife)** | Repetitive work: login per channel, upload videos, think of titles/descriptions, create thumbnails, monitor performance at 24h and 72h marks | Cannot focus on strategic/creative work |
| **System** | Sequential upload process frequently interrupted by connection issues or human error, causing missed publish times | Unreliable content pipeline |

**Case Study — "The Hybrid-Automation Flow":**

| Channel | Genre | Thumbnail Requirement | Tone |
|---------|-------|----------------------|------|
| Channel A | Lofi | High-contrast, retro typography | Cool, muted |
| Channel B | Oud Fusion Jazz | Arabic typography, warm color palette | Warm, earthy |

The system must automatically distinguish these presets and never force a one-style-fits-all approach.

### 1.3 Solution Overview

**"Wife as Supervisor" Operational Model:**

The system transforms the Supervisor's role from "Technical Operator" to "Strategic Supervisor" through autonomous AI preparation and minimalist human decision points.

```
Editor renders ──► OMV Folder ──► AI Detection ──► Screenshot + Metadata + Thumbnail
                                                          │
                                                          ▼
                                              Telegram Notification (Minimalist)
                                                          │
                              ┌───────────────────────────┼───────────────────────────┐
                              ▼                           ▼                           ▼
                         [Approve]                   [Edit]                      [Discard]
                              │                           │                           │
                              ▼                           ▼                           ▼
                         Enter Queue              Open Dashboard              Remove Draft
                    (Sequential Upload)         (Modify Draft)              (Keep File on OMV)
```

### 1.4 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time saved per video (Supervisor) | 90% reduction | Compare manual vs. supervised workflow |
| Upload success rate | > 95% | Failed uploads / total attempts |
| Auto-approve confidence | > 80% | AI confidence score accuracy |
| Anomaly detection accuracy | > 90% | True positives / total alerts |
| Queue downtime (non-copyright) | < 1% | Time queue is stuck / total time |
| Supervisor dashboard visits | < 2 per day (routine) | For approvals, Telegram should suffice |

---

## 2. User Personas

### 2.1 Persona 1: The Editor (Content Creator)

| Attribute | Detail |
|-----------|--------|
| **Name** | Nandito (User) |
| **Role** | Video Editor + Ideator |
| **Technical Skill** | Intermediate (knows rendering, file management) |
| **Goal** | Focus on creating content, not operational logistics |
| **Workflow** | Renders multiple videos in a day, copies to OMV, moves on to ideation |
| **System Interaction** | Minimal — only copies files to OMV |
| **Pain Point** | Don't want to be bothered with upload processes after rendering |

**User Story:**
> "As an Editor, I want to copy my rendered videos to OMV and forget about them, so that I can focus entirely on creating the next batch of content."

### 2.2 Persona 2: The Supervisor (Channel Manager)

| Attribute | Detail |
|-----------|--------|
| **Name** | Istri (User's Wife) |
| **Role** | Channel Supervisor |
| **Technical Skill** | Basic (comfortable with Telegram, simple web UI) |
| **Goal** | Oversee all channels efficiently without manual operational work |
| **Workflow** | Receives Telegram notifications, approves/edits/discards drafts, reviews 08:00 reports |
| **System Interaction** | Primarily Telegram; dashboard for complex edits |
| **Pain Point** | Currently overwhelmed by repetitive per-channel tasks |

**User Stories:**
> "As a Supervisor, I want to approve video uploads from Telegram with one tap, so that I don't need to open a web dashboard for routine tasks."

> "As a Supervisor, I want to receive a concise performance report every morning at 8 AM, so that I can quickly understand how all channels are performing."

> "As a Supervisor, I want the AI to alert me immediately when something is wrong (low CTR, copyright claim), so that I can take action before it affects other channels."

---

## 3. Feature Specifications

### 3.1 Feature: File Watcher & Ingestion (OMV Sync)

**ID:** F-001
**Priority:** P0 (Critical)
**Status:** Required for MVP

**Description:**
Automatically detect new video files copied to the OMV NAS shared folders. Distinguish between files currently being copied (incomplete) and files that are fully written (ready for processing).

**Requirements:**

| ID | Requirement | Priority |
|----|-------------|----------|
| F-001-R1 | Monitor `/nas/[channel_name]/` folders for new `.mp4`, `.mov`, `.avi` files | P0 |
| F-001-R2 | Distinguish copying-in-progress vs. completed files via file size stability check (stable for 5 seconds) | P0 |
| F-001-R3 | Support hybrid trigger: automatic periodic scan (every 2 minutes) + manual "Scan Now" button in dashboard | P0 |
| F-001-R4 | Extract basic file metadata: filename, file size, duration (via ffprobe), creation time | P0 |
| F-001-R5 | Map detected file to correct channel based on parent folder name | P0 |
| F-001-R6 | Create database record with status `detected` upon successful detection | P0 |
| F-001-R7 | Send Telegram notification: "🎵 Video baru di [Channel Name]: [filename]" | P0 |

**Acceptance Criteria:**
- A 500MB video file copied to `/nas/lofi_chill/` is detected within 10 seconds of copy completion.
- A file still being copied is NOT processed (no false positives).
- Manual scan button triggers immediate folder check.

---

### 3.2 Feature: Screenshot Extraction

**ID:** F-002
**Priority:** P0
**Status:** Required for MVP

**Description:**
Extract a representative frame from the video at second 30 to avoid intro/logo segments. This screenshot serves as the base image for AI thumbnail generation.

**Requirements:**

| ID | Requirement | Priority |
|----|-------------|----------|
| F-002-R1 | Extract frame at exactly 00:00:30 using ffmpeg | P0 |
| F-002-R2 | Save screenshot as `.jpg` in `/nas/[channel_name]/thumbnails/screenshots/` | P0 |
| F-002-R3 | Resolution: 1280x720 (YouTube thumbnail standard) | P0 |
| F-002-R4 | Handle edge cases: video shorter than 30s (use 50% mark), corrupted video (log error) | P1 |
| F-002-R5 | Screenshot filename: `{video_filename}_frame30.jpg` | P0 |

**Acceptance Criteria:**
- A 5-minute video produces a clear 1280x720 JPG at second 30.
- A 20-second video produces a screenshot at second 10 (50% mark).
- Corrupted video logs error and notifies Supervisor without crashing the watcher.

---

### 3.3 Feature: AI Thumbnail Generator

**ID:** F-003
**Priority:** P0
**Status:** Required for MVP

**Description:**
Generate thumbnail variations using AI image restyling based on the screenshot and channel-specific style presets. Uses Cloudflare Workers AI via free-image-generation-api.

**Requirements:**

| ID | Requirement | Priority |
|----|-------------|----------|
| F-003-R1 | Read channel's `thumbnail_style` preset (e.g., "lofi-retro", "jazz-arabic") | P0 |
| F-003-R2 | Generate 3 thumbnail options per video using AI restyling API | P0 |
| F-003-R3 | First-time channel: present 3 style options to Supervisor for selection | P0 |
| F-003-R4 | After style selected: auto-use that style for all future videos on that channel | P0 |
| F-003-R5 | Supervisor can request "Generate 3 new styles" anytime | P1 |
| F-003-R6 | Each thumbnail gets a confidence score based on visual quality metrics | P1 |
| F-003-R7 | Store all generated thumbnails in `/nas/[channel_name]/thumbnails/generated/` | P0 |

**Style Preset Examples:**

| Channel Genre | Style Name | Prompt Pattern |
|--------------|------------|----------------|
| Lofi | `lofi-retro` | "High-contrast, retro typography, muted cool tones, grain texture, minimalist" |
| Oud Fusion Jazz | `jazz-arabic` | "Warm earthy palette, large Arabic calligraphy, golden accents, elegant" |
| Ambient | `ambient-ethereal` | "Soft gradients, ethereal lighting, subtle text, dreamy atmosphere" |

**Acceptance Criteria:**
- First video on a new channel presents 3 style options in the dashboard.
- After style selection, subsequent videos automatically use that style.
- Generated thumbnails are 1280x720 JPG files.
- API failure falls back to using the raw screenshot (with notification).

---

### 3.4 Feature: AI Metadata Generator

**ID:** F-004
**Priority:** P0
**Status:** Required for MVP

**Description:**
Generate title, description, and tags based on channel preset templates, genre, filename analysis, and screenshot content.

**Requirements:**

| ID | Requirement | Priority |
|----|-------------|----------|
| F-004-R1 | Parse filename for hints (e.g., "lofi_relax_study_01.mp4" → genre: lofi, mood: relax, activity: study) | P0 |
| F-004-R2 | Apply channel preset template for title format | P0 |
| F-004-R3 | Generate description with: intro paragraph, timestamps, social links (from channel profile), hashtags | P0 |
| F-004-R4 | Generate 10–15 relevant tags based on genre + filename + description | P0 |
| F-004-R5 | Language: English (primary, for worldwide audience) | P0 |
| F-004-R6 | Title max 100 characters (YouTube limit) | P0 |
| F-004-R7 | Each draft gets Confidence Score (0–100%) | P0 |
| F-004-R8 | Support A/B testing: generate 2 title variations for alternate videos | P1 |

**Title Template Examples:**

| Channel | Template | Example Output |
|---------|----------|----------------|
| Lofi Chill | `{mood} Lofi Beats for {activity} \| {duration}` | "Relaxing Lofi Beats for Study \| 3 Hours" |
| Oud Jazz | `{genre} Fusion: {mood} \| {artist_name}` | "Oud Jazz Fusion: Midnight Meditation \| Nandito" |

**Acceptance Criteria:**
- Metadata is generated within 30 seconds of screenshot extraction.
- Title is under 100 characters.
- Description includes channel-specific social links.
- Tags are relevant to the video content and genre.

---

### 3.5 Feature: Telegram Integration

**ID:** F-005
**Priority:** P0
**Status:** Required for MVP

**Description:**
Minimalist Telegram bot notifications with inline action buttons for Supervisor approval workflow.

**Requirements:**

| ID | Requirement | Priority |
|----|-------------|----------|
| F-005-R1 | Send notification when video is ready for review (after metadata + thumbnail generated) | P0 |
| F-005-R2 | Notification format: 1–2 sentences + inline buttons [Approve] [Edit] [Discard] | P0 |
| F-005-R3 | Notification includes: video name, channel name, draft title, scheduled upload time | P0 |
| F-005-R4 | [Approve] → Video enters upload queue, confirmation message sent | P0 |
| F-005-R5 | [Edit] → Link to dashboard with pre-filled draft data | P0 |
| F-005-R6 | [Discard] → Remove draft, file stays on OMV, confirmation sent | P0 |
| F-005-R7 | Callback data format: `action:video_id:channel_id` | P0 |
| F-005-R8 | Support conversation handler for schedule override ([Change Time] button) | P1 |
| F-005-R9 | Support [Generate New Styles] for thumbnail regeneration | P1 |

**Notification Template:**
```
🎵 [Channel Name]
"Video Title Here" (Draft)
📅 Jadwal: 10:00 WIB

[Approve] [Edit] [Discard]
```

**Acceptance Criteria:**
- Supervisor receives notification within 1 minute of draft completion.
- [Approve] button works without opening dashboard.
- [Edit] opens dashboard in browser with correct video pre-selected.
- All callback actions execute within 3 seconds.

---

### 3.6 Feature: Sequential Upload Queue

**ID:** F-006
**Priority:** P0
**Status:** Required for MVP

**Description:**
Manage YouTube uploads in a strict single-line queue with retry logic, time override management, and channel priority handling.

**Requirements:**

| ID | Requirement | Priority |
|----|-------------|----------|
| F-006-R1 | Only ONE active upload at any time across ALL channels | P0 |
| F-006-R2 | Celery task queue with Redis broker | P0 |
| F-006-R3 | Upload via YouTube Data API v3 (status: private) | P0 |
| F-006-R4 | Retry failed uploads automatically: 5 attempts with exponential backoff | P0 |
| F-006-R5 | After 5 failures, notify Supervisor via Telegram | P0 |
| F-006-R6 | Time-Override: If Channel A (preferred 10:00) finishes at 14:30, Channel B starts immediately | P0 |
| F-006-R7 | Queue status visible in dashboard (waiting, uploading, completed, failed) | P0 |
| F-006-R8 | Upload includes: video file, thumbnail, title, description, tags, category | P0 |
| F-006-R9 | Set "Made for Kids" flag based on channel preset | P0 |

**Queue State Machine:**

```
detected ──► staging ──► approved ──► queued ──► uploading ──► uploaded
                                              │
                                              ▼
                                           failed ──► retry (max 5) ──► failed_permanent
```

**Acceptance Criteria:**
- Two approved videos from different channels never upload simultaneously.
- Failed upload retries automatically within 5 minutes.
- Permanent failure (after 5 retries) triggers Telegram notification.
- Queue processes next video immediately after current upload completes.

---

### 3.7 Feature: Channel Management

**ID:** F-007
**Priority:** P0
**Status:** Required for MVP

**Description:**
Multi-channel management with profile selector, per-channel presets, and individual GCP credential management.

**Requirements:**

| ID | Requirement | Priority |
|----|-------------|----------|
| F-007-R1 | Channel Profile Selector UI (similar to Chrome profile selector) | P0 |
| F-007-R2 | Per-channel settings: name, genre, folder path, preferred upload time | P0 |
| F-007-R3 | Per-channel metadata preset: title template, description template, default tags | P0 |
| F-007-R4 | Per-channel thumbnail preset: style name, style description | P0 |
| F-007-R5 | Per-channel GCP credentials: client_secret.json path, project ID | P0 |
| F-007-R6 | Auto-approve toggle per channel | P1 |
| F-007-R7 | Channel activation/deactivation toggle | P0 |
| F-007-R8 | "Made for Kids" default setting per channel | P0 |
| F-007-R9 | Social links per channel (for description template) | P0 |

**Acceptance Criteria:**
- New channel can be added with all presets in under 5 minutes.
- Channel selector filters all dashboard views to selected channel.
- Deactivating a channel pauses its uploads but preserves data.

---

### 3.8 Feature: Analytics & Performance Monitoring

**ID:** F-008
**Priority:** P1
**Status:** Post-MVP (Phase 2)

**Description:**
Collect, analyze, and report video performance metrics. Use Qdrant vector database for pattern recognition and AI-generated insights.

**Requirements:**

| ID | Requirement | Priority |
|----|-------------|----------|
| F-008-R1 | Collect views at 24h and 72h after publish | P1 |
| F-008-R2 | Collect CTR (Click-Through Rate) | P1 |
| F-008-R3 | Collect AVD (Average View Duration) in seconds | P1 |
| F-008-R4 | Collect likes, comments count | P1 |
| F-008-R5 | Store performance vectors in Qdrant for similarity comparison | P1 |
| F-008-R6 | Compare current video performance against channel average | P1 |
| F-008-R7 | Detect anomalies: CTR < 2%, views 24h < 100, AVD drop > 20% from average | P1 |
| F-008-R8 | Generate actionable insights (not just raw numbers) | P1 |
| F-008-R9 | Accumulative report sent daily at 08:00 WIB via Telegram | P1 |

**Insight Examples:**

| Condition | Insight Message |
|-----------|----------------|
| CTR < 2% | "CTR video ini 1.8%, di bawah rata-rata channel (3.2%). Thumbnail mungkin kurang kontras. Coba style 'high-contrast' untuk video berikutnya." |
| AVD drop at 30s | "5 video terakhir penonton drop di detik 30. Mungkin intro terlalu panjang atau audio kurang menarik?" |
| Views 24h < 100 | "Views 24 jam di bawah 100. Judul mungkin kurang menarik. Coba variasi dengan kata kunci yang lebih spesifik." |
| High engagement | "🎉 Video ini performa di atas rata-rata! Judul 'X' dan thumbnail style 'Y' berhasil. Pertahankan pola ini." |

**Acceptance Criteria:**
- Analytics collected automatically without manual intervention.
- Anomaly alerts sent within 1 hour of detection.
- 08:00 report is scannable (bullet points, emojis, key metrics only).

---

### 3.9 Feature: Dashboard (Web UI)

**ID:** F-009
**Priority:** P0
**Status:** Required for MVP

**Description:**
Web-based dashboard for channel management, video staging, queue monitoring, and analytics visualization. Used when Telegram actions are insufficient (complex edits, bulk operations).

**Pages:**

| Page | Purpose | Priority |
|------|---------|----------|
| **Global Dashboard** | Health bar, task feed, upload schedule, system alerts | P0 |
| **Channel List** | All channels, status, quick actions | P0 |
| **Channel Detail** | Per-channel settings, presets, analytics | P0 |
| **Staging Area** | Videos awaiting approval, thumbnail preview, metadata editor | P0 |
| **Video Detail** | Full video info, metadata history, analytics, queue status | P0 |
| **Queue Manager** | Real-time queue status, priority override, history | P0 |
| **Schedule Calendar** | Visual calendar of upcoming uploads per channel | P1 |
| **Analytics Page** | Charts, graphs, performance trends per channel | P1 |
| **Log Viewer** | System logs, error history, API call logs | P0 |
| **GCP Manager** | Quota usage per project, token status | P1 |
| **Settings** | User preferences, notification settings, system config | P0 |

**Dashboard Design Principles:**
- **Modular Panel** design (inspired by Linear/Vercel).
- Dark mode by default (reduces eye strain for daily use).
- Channel context switcher in sidebar.
- All actions have immediate visual feedback.
- Mobile-responsive for on-the-go supervision.

---

### 3.10 Feature: Safety & Fail-Safe

**ID:** F-010
**Priority:** P0
**Status:** Required for MVP

**Description:**
Protect channels from catastrophic failures through automated safety mechanisms.

**Requirements:**

| ID | Requirement | Priority |
|----|-------------|----------|
| F-010-R1 | Auto-pause ALL upload queues if Copyright Claim detected on ANY video | P0 |
| F-010-R2 | Send critical alert to Supervisor via Telegram with claim details | P0 |
| F-010-R3 | Queue resumes only after manual Supervisor [Resume] action | P0 |
| F-010-R4 | Monitor GCP API quota per project, alert at 80% usage | P1 |
| F-010-R5 | Alert when OMV storage exceeds 80% capacity | P1 |
| F-010-R6 | Validate video file integrity before upload (corruption check) | P0 |
| F-010-R7 | Log all API errors with structured JSON for debugging | P0 |

**Acceptance Criteria:**
- Copyright claim on Channel A stops uploads on Channels B, C, D, etc. immediately.
- Supervisor receives critical alert within 1 minute.
- Queue cannot be resumed without manual confirmation.

---

### 3.11 Feature: Metadata Experimentation & A/B Testing

**ID:** F-011
**Priority:** P2
**Status:** Post-MVP (Phase 3)

**Description:**
Enable the Supervisor to experiment with different metadata styles and track which performs better.

**Requirements:**

| ID | Requirement | Priority |
|----|-------------|----------|
| F-011-R1 | Metadata versioning: save each draft version with timestamp | P2 |
| F-011-R2 | A/B Test: mark videos with different title/thumbnail styles | P2 |
| F-011-R3 | Compare performance between A/B variants after 72h | P2 |
| F-011-R4 | AI suggests which style to adopt based on A/B results | P2 |
| F-011-R5 | Confidence Score evolution tracking | P2 |
| F-011-R6 | AI-generated "skor kualitas" (1–10) for metadata drafts | P2 |

---

## 4. User Flows

### 4.1 Flow 1: Editor — Render & Copy

```
1. Editor renders video in editing software (Premiere, DaVinci, etc.)
2. Editor copies file to /nas/[channel_name]/[video_filename].mp4
3. System auto-detects, processes, and notifies Supervisor
4. Editor moves on to next task — ZERO system interaction required
```

### 4.2 Flow 2: Supervisor — Approve via Telegram

```
1. Supervisor receives Telegram notification:
   "🎵 Lofi Chill
    'Relaxing Study Beats | 3 Hours' (Draft)
    📅 Jadwal: 10:00 WIB
    [Approve] [Edit] [Discard]"

2. Supervisor taps [Approve]
3. System confirms: "✅ Video masuk antrean upload"
4. Video uploads when queue reaches it
5. Supervisor receives confirmation when upload complete
```

### 4.3 Flow 3: Supervisor — Edit via Dashboard

```
1. Supervisor receives Telegram notification
2. Supervisor taps [Edit]
3. Browser opens dashboard at Video Detail page
4. Supervisor modifies title, description, tags, or thumbnail
5. Supervisor clicks [Save & Approve]
6. Video enters upload queue
```

### 4.4 Flow 4: AI — Autonomous Preparation

```
1. File Watcher detects new video in /nas/[channel_name]/
2. System validates file is complete (size stable)
3. ffmpeg extracts screenshot at second 30
4. AI reads channel preset (genre, style, template)
5. AI generates 3 thumbnail options via Cloudflare Workers AI
6. AI generates metadata (title, description, tags) with Confidence Score
7. System creates draft records in database
8. Telegram notification sent to Supervisor
9. Video status: staging (awaiting approval)
```

### 4.5 Flow 5: Queue — Sequential Upload

```
1. Video approved by Supervisor (status: approved)
2. Queue Manager adds to Celery task queue
3. When queue reaches this video (status: uploading):
   a. Load channel's OAuth credentials
   b. Upload video to YouTube (private)
   c. Upload thumbnail
   d. Set metadata (title, description, tags)
   e. Verify upload success
4. Status changes to uploaded, YouTube video ID stored
5. Next video in queue starts immediately
6. Analytics tracking begins (scheduled for 24h and 72h)
```

### 4.6 Flow 6: Analytics — Daily Report

```
1. At 08:00 WIB, system collects all analytics data
2. AI analyzes performance vs. historical patterns (Qdrant)
3. System generates accumulative report:
   - Channel summaries (views, growth)
   - Anomaly alerts (if any)
   - AI suggestions for improvement
4. Report sent via Telegram in scannable format
5. Data stored for long-term trend analysis
```

---

## 5. Out of Scope (Explicitly Excluded)

| Feature | Reason | Future Consideration |
|---------|--------|---------------------|
| Video rendering/editing | Editor handles this externally | Never in scope |
| Public/published scheduling (initially) | MVP only supports private upload | Phase 2: schedule publish |
| Comment/reply management | Out of scope for orchestrator | Possible future feature |
| Community post management | Out of scope | Future consideration |
| Multi-video bulk upload | Sequential queue makes this irrelevant | N/A |
| Auto-deletion of uploaded videos from OMV | Explicitly forbidden by user | Never in scope |
| AI video generation | User creates content manually | Never in scope |
| Cross-platform (TikTok, Instagram) | YouTube-only for MVP | Phase 3 |
| Real-time analytics streaming | Polling-based is sufficient | Future |
| AI-generated video content | User is the creator | Never in scope |

---

## 6. Assumptions & Dependencies

### 6.1 Assumptions

| ID | Assumption | Risk if Wrong |
|----|-----------|---------------|
| A-001 | Editor always copies videos to correct `/nas/[channel_name]/` folder | Wrong channel upload |
| A-002 | OMV VM is always accessible from Ubuntu VM via network mount | System cannot ingest files |
| A-003 | All videos are original content (no copyright issues) | Copyright claims unlikely |
| A-004 | Supervisor has Telegram installed and notifications enabled | Missed approvals |
| A-005 | free-image-generation-api (Cloudflare) remains available | Thumbnail generation fails |
| A-006 | Each channel has its own GCP project with API enabled | Quota issues |

### 6.2 Dependencies

| ID | Dependency | Owner |
|----|-----------|-------|
| D-001 | YouTube Data API v3 availability | Google |
| D-002 | YouTube Analytics API availability | Google |
| D-003 | Cloudflare Workers AI API availability | Cloudflare |
| D-004 | Telegram Bot API availability | Telegram |
| D-005 | Proxmox + 2 VMs operational | User |
| D-006 | OMV to Ubuntu VM network connectivity | User/Network |

---

## 7. Glossary

| Term | Definition |
|------|-----------|
| **OMV** | OpenMediaVault — NAS operating system running on VM 1 |
| **Supervisor** | User's wife — channel manager who approves uploads |
| **Editor** | User (Nandito) — content creator who renders videos |
| **Staging** | State where video waits for Supervisor approval |
| **Queue** | Sequential line of approved videos waiting to upload |
| **Draft** | AI-generated metadata/thumbnail pending approval |
| **Preset** | Channel-specific template for metadata/thumbnail style |
| **OMV** | OpenMediaVault NAS on VM 1 (4TB HDD) |
| **VM** | Virtual Machine on Proxmox (OMV + Ubuntu Server) |
| **GCP** | Google Cloud Platform project per channel |
| **CTR** | Click-Through Rate — percentage of impressions that result in clicks |
| **AVD** | Average View Duration — average time viewers watch the video |
| **Qdrant** | Vector database for pattern recognition and similarity search |
| **WIB** | Western Indonesian Time (UTC+7) — user's timezone |
