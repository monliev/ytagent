# UI_SPEC.md

## YTAgent — User Interface Specification

> **Version:** 1.0.0
> **Date:** 2025-06-26
> **Status:** Approved
> **Framework:** React 18 + Tailwind CSS + shadcn/ui

---

## 1. Design System

### 1.1 Design Philosophy

The YTAgent dashboard follows a **"Supervisory Command Center"** metaphor — clean, information-dense, and optimized for quick decision-making. The Supervisor should be able to assess the health of 10–30 channels in a single glance.

**Key Principles:**
- **Dark mode by default** — reduces eye strain for daily use
- **Channel-centric navigation** — all views are scoped to a selected channel
- **Minimal chrome** — maximize content area
- **Status at a glance** — color-coded indicators, progress bars, counters
- **Mobile-responsive** — for on-the-go supervision

### 1.2 Color Palette

```css
/* Tailwind Configuration */
module.exports = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        /* Base */
        background: '#0f1115',      /* Main background */
        surface: '#1a1d24',         /* Card/panel background */
        surfaceHover: '#22262e',    /* Hover state */
        border: '#2a2e38',          /* Borders */
        
        /* Text */
        textPrimary: '#e8eaf0',     /* Headings, primary text */
        textSecondary: '#8b92a8',   /* Descriptions, metadata */
        textMuted: '#5a6070',       /* Timestamps, placeholders */
        
        /* Status Colors */
        statusSuccess: '#22c55e',   /* Uploaded, healthy */
        statusWarning: '#f59e0b',   /* Pending, needs attention */
        statusError: '#ef4444',     /* Failed, critical */
        statusInfo: '#3b82f6',      /* Processing, active */
        statusNeutral: '#6b7280',   /* Inactive, discarded */
        
        /* Channel Genre Colors (for visual distinction) */
        genreLofi: '#8b9dc3',       /* Muted blue-grey */
        genreJazz: '#d4a373',       /* Warm gold */
        genreAmbient: '#a8d5ba',    /* Soft green */
        genreElectronic: '#c77dff', /* Purple */
        genreClassical: '#e9c46a',  /* Yellow-gold */
      }
    }
  }
}
```

### 1.3 Typography

| Level | Font | Size | Weight | Usage |
|-------|------|------|--------|-------|
| H1 | Inter | 24px | 700 | Page titles |
| H2 | Inter | 20px | 600 | Section headers |
| H3 | Inter | 16px | 600 | Card titles |
| Body | Inter | 14px | 400 | General text |
| Small | Inter | 12px | 400 | Metadata, timestamps |
| Mono | JetBrains Mono | 13px | 400 | Logs, IDs, technical data |

### 1.4 Spacing System

Based on 4px grid:
- `xs`: 4px
- `sm`: 8px
- `md`: 16px
- `lg`: 24px
- `xl`: 32px
- `2xl`: 48px

### 1.5 Component Library

Base components from **shadcn/ui**:

| Component | shadcn/ui | Customizations |
|-----------|-----------|----------------|
| Button | ✅ | Status color variants |
| Card | ✅ | Dark surface background |
| Input | ✅ | Dark theme styling |
| Textarea | ✅ | Auto-resize for descriptions |
| Select | ✅ | Channel selector styling |
| Dialog | ✅ | Large modal for video detail |
| Dropdown | ✅ | Action menus |
| Table | ✅ | TanStack Table integration |
| Tabs | ✅ | Channel detail sections |
| Badge | ✅ | Status indicators |
| Avatar | ✅ | Channel profile images |
| Toast | ✅ | Sonner for notifications |
| Skeleton | ✅ | Loading states |
| Progress | ✅ | Upload progress |
| Calendar | ✅ | Schedule view |
| Chart | ❌ (custom) | Recharts integration |
| VideoCard | ❌ (custom) | Thumbnail + metadata preview |
| QueueItem | ❌ (custom) | Queue status display |
| InsightCard | ❌ (custom) | AI insight display |

---

## 2. Layout Structure

### 2.1 Global Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Sidebar (240px)        │  Main Content Area                     │
│  ─────────────────────  │  ───────────────────────────────────  │
│                         │                                        │
│  [Channel Selector]     │  [Header Bar]                         │
│  ┌─────────────────┐   │  Breadcrumb | Actions | User           │
│  │ ▼ Lofi Chill    │   │  ───────────────────────────────────  │
│  │   Oud Jazz      │   │                                        │
│  │   Ambient Vibes │   │  [Page Content]                       │
│  └─────────────────┘   │                                        │
│                         │                                        │
│  NAVIGATION             │                                        │
│  ─────────────────────  │                                        │
│  📊 Dashboard           │                                        │
│  🎬 Staging Area        │                                        │
│  📁 Queue Manager       │                                        │
│  📅 Schedule            │                                        │
│  📈 Analytics           │                                        │
│  ⚙️ Channel Settings    │                                        │
│  📋 Logs                │                                        │
│                         │                                        │
│  ─────────────────────  │                                        │
│  🔔 Notifications (3)   │                                        │
│  👤 Supervisor          │                                        │
└─────────────────────────┴────────────────────────────────────────┘
```

### 2.2 Channel Selector Component

**Visual Design:** Chrome Profile Selector-inspired dropdown

```
┌────────────────────────────────────┐
│  [Avatar]  Lofi Chill     ▼        │
├────────────────────────────────────┤
│  Switch Channel                    │
├────────────────────────────────────┤
│  [🎵] Lofi Chill         ● Active  │
│  [🎷] Oud Fusion Jazz              │
│  [🌊] Ambient Vibes                │
│  [⚡] Electronic Beats              │
├────────────────────────────────────┤
│  + Add New Channel                 │
└────────────────────────────────────┘
```

**Behavior:**
- Clicking a channel switches ALL dashboard views to that channel's context
- Selected channel persists across page navigation (Zustand store)
- "All Channels" option at top for global views

---

## 3. Page Specifications

### 3.1 Page: Global Dashboard (`/`)

**Purpose:** At-a-glance health overview of all channels.

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│  Global Dashboard                                  [Refresh]    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  HEALTH BAR     │  │ TODAY'S TASKS   │  │  QUICK STATS    │ │
│  │  ─────────────  │  │  ─────────────  │  │  ─────────────  │ │
│  │                 │  │                 │  │                 │ │
│  │  [████░░░░░░]   │  │ • 3 videos need │  │  Channels: 15   │ │
│  │  12 Active      │  │   approval      │  │  Active: 12     │ │
│  │   2 Warning     │  │ • 1 upload in   │  │  Pending: 3     │ │
│  │   1 Error       │  │   progress      │  │  Uploads Today:8│ │
│  │                 │  │ • 2 reports at  │  │                 │ │
│  │                 │  │   08:00         │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  CHANNEL STATUS GRID                                    │   │
│  │  ─────────────────────────────────────────────────────  │   │
│  │                                                         │   │
│  │  [🎵 Lofi]    [🎷 Jazz]   [🌊 Ambient]  [⚡ Electro]   │   │
│  │  ● Active     ● Active    ⚠ Uploading   ● Active      │   │
│  │  12 videos    8 videos    1 pending     15 videos     │   │
│  │  Today: 1     Today: 1    Today: 0      Today: 2      │   │
│  │                                                         │   │
│  │  [🎹 Piano]   [🎸 Guitar] [🥁 Drums]    [🎻 Strings]   │   │
│  │  ● Active     ● Active    ● Active      ● Active      │   │
│  │  ...          ...         ...           ...           │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  UPLOAD SCHEDULE (Next 24h)                             │   │
│  │  ─────────────────────────────────────────────────────  │   │
│  │                                                         │   │
│  │  10:00  [🎵] Lofi Chill - "Study Beats"                 │   │
│  │  14:00  [🎷] Oud Jazz - "Midnight Fusion"               │   │
│  │  18:00  [🌊] Ambient - "Ocean Dreams"                   │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  🚨 SYSTEM ALERTS                                       │   │
│  │  ─────────────────────────────────────────────────────  │   │
│  │  ⚠️ Channel "Oud Jazz" quota 85% — consider switching   │   │
│  │     GCP project                                         │   │
│  │  ⚠️ 2 videos failed upload (auto-retrying)              │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Channel Status Card:**

| Element | Display |
|---------|---------|
| Icon | Genre emoji + channel name |
| Status Dot | Green (active) / Yellow (warning) / Red (error) / Blue (uploading) |
| Video Count | Total videos in channel |
| Today's Uploads | Count uploaded today |
| Last Upload | Time ago |

---

### 3.2 Page: Staging Area (`/staging`)

**Purpose:** Review and approve videos awaiting upload.

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│  🎬 Staging Area — Lofi Chill                      [Filter ▼]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  FILTERS: [All] [Needs Approval] [Ready] [Discarded]   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  VIDEO CARD (Expanded)                                  │   │
│  │  ┌──────────────┐  ┌─────────────────────────────────┐  │   │
│  │  │              │  │ "Relaxing Lofi Beats for Study  │  │   │
│  │  │  [Thumbnail  │  │  | 3 Hours"                      │  │   │
│  │  │   Preview]   │  │                                   │  │   │
│  │  │              │  │  📄 Metadata                      │  │   │
│  │  │  [View All   │  │  Title: Relaxing Lofi Beats...   │  │   │
│  │  │   Thumbnails]│  │  Tags: #lofi #study #beats...    │  │   │
│  │  │              │  │  Confidence: 87% 🟢               │  │   │
│  │  └──────────────┘  │                                   │  │   │
│  │                     │  🖼️ Thumbnail Options             │  │   │
│  │  [○] [○] [○]       │  [Thumb 1] [Thumb 2] [Thumb 3]   │  │   │
│  │  Style: lofi-retro  │  ◄  ►  carousel                 │  │   │
│  │                     │                                   │  │   │
│  │  File: video_01.mp4 │  📅 Schedule: 10:00 WIB           │  │   │
│  │  Size: 450 MB       │  [Change]                         │  │   │
│  │  Duration: 3:00:00  │                                   │  │   │
│  │                     │  [✅ Approve] [✏️ Edit] [🗑️ Discard]│  │   │
│  │  Detected: 2m ago   │                                   │  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  VIDEO CARD (Collapsed)                                 │   │
│  │  [Thumb] "Midnight Jazz Session" — Confidence: 82%      │   │
│  │  [✅ Approve] [✏️ Edit] [🗑️ Discard]                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Video Card Interactions:**

| Action | Behavior |
|--------|----------|
| Click card | Expand/collapse details |
| Click thumbnail | Open full-size preview modal |
| [Approve] | Status → approved, enters queue, confirmation toast |
| [Edit] | Open Video Detail page with editable forms |
| [Discard] | Confirmation dialog → status → discarded |
| [Change] (schedule) | Date/time picker dropdown |
| Thumbnail carousel | Swipe/click through 3 options, select one |

---

### 3.3 Page: Video Detail (`/videos/:id`)

**Purpose:** Full video information with editing capabilities.

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Back to Staging                                               │
│  "Relaxing Lofi Beats for Study | 3 Hours"              [Edit]  │
├─────────────────────────────────────────────────────────────────┤
│  [Status: STAGING]  Channel: Lofi Chill  Uploaded: --          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  TABS: [Overview] [Metadata] [Thumbnails] [Analytics] [History] │
│                                                                 │
│  ─── OVERVIEW TAB ───                                           │
│  ┌──────────────────┐  ┌──────────────────────────────────────┐│
│  │                  │  │  VIDEO INFO                          ││
│  │   [LARGE         │  │  ────────────────────────────────── ││
│  │    THUMBNAIL     │  │  Filename: video_01.mp4             ││
│  │    PREVIEW]      │  │  File Size: 450 MB                  ││
│  │                  │  │  Duration: 3:00:00                  ││
│  │                  │  │  Resolution: 1920x1080              ││
│  │  [View Screenshot│  │  Frame 30: [View]                   ││
│  │   at 00:00:30]   │  │                                     ││
│  │                  │  │  UPLOAD STATUS                      ││
│  └──────────────────┘  │  ────────────────────────────────── ││
│  ┌──────────────────┐  │  Status: ⏳ Waiting for approval     ││
│  │ 3 THUMBNAIL      │  │  Queue Position: --                 ││
│  │ OPTIONS          │  │  Scheduled: 10:00 WIB               ││
│  │ [○] [○] [○]      │  │  YouTube ID: --                     ││
│  │ Select one       │  │                                     ││
│  └──────────────────┘  │  ACTIONS                            ││
│                        │  [✅ Approve] [🗑️ Discard]          ││
│                        └──────────────────────────────────────┘│
│                                                                 │
│  ─── METADATA TAB ─── (Editable when in staging)               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Title:     [Relaxing Lofi Beats for Study | 3 Hours]  │   │
│  │  Description: [Textarea with template...]               │   │
│  │  Tags:      [lofi, study, beats, relax...]             │   │
│  │  Language:  [English ▼]                                 │   │
│  │  Made for kids: [ ] No                                  │   │
│  │                                                         │   │
│  │  [💡 AI Suggestions]                                    │   │
│  │  "Judul ini sudah bagus (score: 8/10). Untuk CTR lebih  │   │
│  │   tinggi, coba tambahkan kata 'Focus' di awal judul."   │   │
│  │                                                         │   │
│  │  [💾 Save Changes] [↩️ Revert to AI Draft]              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3.4 Page: Queue Manager (`/queue`)

**Purpose:** Monitor and manage the upload queue.

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│  📁 Queue Manager                                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  QUEUE STATUS: ● Running  |  Current: Lofi Chill - "Study..."  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ACTIVE UPLOAD                                          │   │
│  │  ─────────────────────────────────────────────────────  │   │
│  │  [Thumbnail]  "Relaxing Lofi Beats..."                  │   │
│  │               Channel: Lofi Chill                       │   │
│  │               Progress: [████████░░░░] 67%               │   │
│  │               Speed: 2.5 MB/s | ETA: 3 min               │   │
│  │               [⏸️ Pause] [❌ Cancel]                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  WAITING IN QUEUE                                       │   │
│  │  ─────────────────────────────────────────────────────  │   │
│  │  #  Channel       Video Title            Schedule  Act  │   │
│  │  1  🎷 Oud Jazz   "Midnight Fusion..."   14:00    ↑↓ ✕  │   │
│  │  2  🌊 Ambient    "Ocean Dreams..."      18:00    ↑↓ ✕  │   │
│  │  3  ⚡ Electronic "Synthwave Night..."    Tomorrow ↑↓ ✕  │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  RECENTLY COMPLETED                                     │   │
│  │  ─────────────────────────────────────────────────────  │   │
│  │  ✅ Lofi Chill  "Study Beats"      09:45  2.3 MB/s    │   │
│  │  ✅ Oud Jazz    "Evening Melody"   08:30  2.1 MB/s    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3.5 Page: Analytics (`/analytics`)

**Purpose:** View performance data and AI insights per channel.

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│  📈 Analytics — Lofi Chill          [7 days ▼] [Export]         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  TOTAL VIEWS    │  │  AVG CTR        │  │  AVG AVD        │ │
│  │  ─────────────  │  │  ─────────────  │  │  ─────────────  │ │
│  │                 │  │                 │  │                 │ │
│  │  12,450         │  │  3.2%           │  │  4m 32s         │ │
│  │  ↑ 15% vs last  │  │  ↑ 0.3%         │  │  ↓ 12s          │ │
│  │     week        │  │                 │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  VIEWS TREND (Line Chart)                               │   │
│  │  ─────────────────────────────────────────────────────  │   │
│  │                                                         │   │
│  │    Views │    ╱╲    ╱╲                                 │   │
│  │    500   │   ╱  ╲  ╱  ╲    ╱╲                          │   │
│  │    400   │  ╱    ╲╱    ╲  ╱  ╲                         │   │
│  │    300   │ ╱              ╲╱   ╲___                     │   │
│  │    200   │╱                      ╲                      │   │
│  │    100   │                            ╲                 │   │
│  │      0   └──────────────────────────────────►           │   │
│  │         Mon  Tue  Wed  Thu  Fri  Sat  Sun               │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  VIDEO PERFORMANCE TABLE                                │   │
│  │  ─────────────────────────────────────────────────────  │   │
│  │  Video Title        Views  CTR   AVD    Status    Act  │   │
│  │  ─────────────────────────────────────────────────────  │   │
│  │  Study Beats        1,245  3.5%  5:20   🟢 Good   👁️   │   │
│  │  Relax Mix            892  2.8%  3:45   🟡 Avg    👁️   │   │
│  │  Focus Music          456  1.8%  2:10   🔴 Low    👁️   │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  🤖 AI INSIGHTS                                         │   │
│  │  ─────────────────────────────────────────────────────  │   │
│  │  💡 "Video 'Focus Music' CTR rendah (1.8%). Thumbnail   │   │
│  │     kurang kontras. Coba style 'high-contrast' untuk    │   │
│  │     video berikutnya."                                  │   │
│  │                                                         │   │
│  │  📊 "AVD rata-rata menurun 12 detik minggu ini.         │   │
│  │     Pertimbangkan untuk memperpendek intro."            │   │
│  │                                                         │   │
│  │  🎉 "Judul dengan pola '{Mood} + {Activity}' memberikan │   │
│  │     CTR 23% lebih tinggi. Pertahankan pola ini!"       │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3.6 Page: Channel Settings (`/channels/:id/settings`)

**Purpose:** Configure channel presets, upload preferences, and GCP credentials.

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚙️ Channel Settings — Lofi Chill                    [Save 💾]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  TABS: [General] [Metadata Preset] [Thumbnail] [GCP] [Advanced] │
│                                                                 │
│  ─── GENERAL TAB ───                                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Channel Name:    [Lofi Chill                    ]      │   │
│  │  Genre:           [Lofi ▼]                              │   │
│  │  Folder Path:     [/mnt/omv/lofi_chill         ] (read) │   │
│  │  Preferred Time:  [10:00 ▼] WIB                         │   │
│  │  Auto-Approve:    [Toggle: OFF]                         │   │
│  │  Made for Kids:   [Toggle: OFF]                         │   │
│  │  Active:          [Toggle: ON]                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ─── METADATA PRESET TAB ───                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Title Template:                                        │   │
│  │  [{mood} Lofi Beats for {activity} | {duration}]        │   │
│  │                                                         │   │
│  │  Description Template:                                  │   │
│  │  [Textarea...]                                          │   │
│  │                                                         │   │
│  │  Default Tags:                                          │   │
│  │  [lofi, chill, study, relax, beats, ambient]            │   │
│  │                                                         │   │
│  │  Social Links:                                          │   │
│  │  Instagram: [@lofichill          ]                      │   │
│  │  Spotify:   [spotify.com/...     ]                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ─── THUMBNAIL TAB ───                                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Style Name:      [lofi-retro                    ]      │   │
│  │                                                         │   │
│  │  AI Prompt:                                             │   │
│  │  [Textarea with prompt...]                              │   │
│  │                                                         │   │
│  │  [🎨 Generate New Style Options]                        │   │
│  │  [Preview Current Style]                                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ─── GCP TAB ───                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Project ID:      [ytagent-lofi-01               ]      │   │
│  │  Client Secret:   [uploaded: client_secret.json ✓]      │   │
│  │  Quota Limit:     10,000 units/day                      │   │
│  │  Quota Used:      6,400 (64%) [████████████░░░░░░]      │   │
│  │  Status:          ● Active                              │   │
│  │  [🔄 Refresh Token] [📊 View Quota Details]             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3.7 Page: Logs (`/logs`)

**Purpose:** View system logs for debugging.

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│  📋 System Logs                            [Filter ▼] [Export]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Filters: [All Levels ▼] [All Services ▼] [Search...      ]    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Time      Level   Service     Event              Video │   │
│  │  ─────────────────────────────────────────────────────  │   │
│  │  10:23:45  INFO    watcher     video_detected     v123 │   │
│  │  10:23:50  INFO    thumbnail   extraction_started v123 │   │
│  │  10:24:12  INFO    thumbnail   generation_complete v123 │   │
│  │  10:24:15  INFO    metadata    generation_complete v123 │   │
│  │  10:24:16  INFO    telegram    notification_sent   v123 │   │
│  │  10:30:02  INFO    upload      upload_started      v123 │   │
│  │  10:35:45  INFO    upload      upload_complete     v123 │   │
│  │  10:35:46  INFO    analytics   tracking_scheduled  v123 │   │
│  │  ─────────────────────────────────────────────────────  │   │
│  │  [Copy JSON] [View Details] [Jump to Video]             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3.8 Page: Schedule Calendar (`/schedule`)

**Purpose:** Visual calendar of upcoming uploads.

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│  📅 Upload Schedule — June 2025                    [◄] [►]      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│     Mon     Tue     Wed     Thu     Fri     Sat     Sun        │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐    │
│  │  26  │ │  27  │ │  28  │ │  29  │ │  30  │ │  1   │ │  2   │    │
│  │      │ │🎵10am│ │🎷2pm │ │🌊6pm │ │⚡10am│ │      │ │      │    │
│  │      │ │Lofi  │ │Jazz  │ │Amb.  │ │Elect │ │      │ │      │    │
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘    │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐    │
│  │  3   │ │  4   │ │  5   │ │  6   │ │  7   │ │  8   │ │  9   │    │
│  │🎵10am│ │🎷2pm │ │🌊6pm │ │⚡10am│ │🎵10am│ │      │ │      │    │
│  │Lofi  │ │Jazz  │ │Amb.  │ │Elect │ │Lofi  │ │      │ │      │    │
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘    │
│                                                                 │
│  Legend: 🎵 Lofi  🎷 Jazz  🌊 Ambient  ⚡ Electronic           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Component Specifications

### 4.1 StatusBadge Component

```tsx
// Displays video/channel status with appropriate color

interface StatusBadgeProps {
  status: VideoStatus | ChannelStatus;
  size?: 'sm' | 'md' | 'lg';
}

// Usage: <StatusBadge status="staging" size="md" />
// Output: [● STAGING] (blue dot + text)
```

| Status | Color | Icon |
|--------|-------|------|
| detected | gray | ○ |
| preparing | blue | ⟳ |
| staging | purple | ⏸ |
| approved | teal | ✓ |
| queued | yellow | ⏳ |
| uploading | blue | ↑ |
| uploaded | green | ✓ |
| failed | red | ✕ |
| discarded | gray | 🗑 |
| error | red | ⚠ |

### 4.2 VideoCard Component

```tsx
interface VideoCardProps {
  video: Video;
  expanded?: boolean;
  onApprove: () => void;
  onEdit: () => void;
  onDiscard: () => void;
}

// States:
// - Collapsed: Thumbnail + Title + Quick Actions
// - Expanded: Full metadata + thumbnails + schedule + actions
```

### 4.3 QueueItem Component

```tsx
interface QueueItemProps {
  task: QueueTask;
  position: number;
  isActive?: boolean;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
  onCancel?: () => void;
}

// States:
// - Pending: Static display
// - Active: Progress bar + speed + ETA
// - Completed: Success state + timestamp
// - Failed: Error message + retry count
```

### 4.4 InsightCard Component

```tsx
interface InsightCardProps {
  insight: PerformanceInsight;
  onDismiss?: () => void;
  onApply?: () => void;
}

// Severity-based styling:
// - info: Blue left border, light blue background
// - warning: Yellow left border, light yellow background
// - critical: Red left border, light red background
```

### 4.5 ChannelSelector Component

```tsx
interface ChannelSelectorProps {
  channels: Channel[];
  selectedId: number | null; // null = "All Channels"
  onSelect: (id: number | null) => void;
}

// Visual: Dropdown with channel avatars, names, and status dots
// Behavior: Selecting a channel updates global context
```

---

## 5. Responsive Breakpoints

| Breakpoint | Width | Layout Changes |
|------------|-------|---------------|
| Mobile | < 640px | Single column, sidebar becomes hamburger menu, cards stack |
| Tablet | 640–1024px | Two-column grid, sidebar collapsible |
| Desktop | > 1024px | Full layout, sidebar always visible |

### 5.1 Mobile Adaptations

| Page | Mobile Layout |
|------|--------------|
| Dashboard | Single column cards, channel grid becomes horizontal scroll |
| Staging | Full-width cards, swipe between thumbnails |
| Video Detail | Tabs become bottom navigation, stacked sections |
| Queue | Simplified list, progress bar only |
| Analytics | Charts become scrollable, table becomes cards |

---

## 6. Animation & Interaction

### 6.1 Transitions

| Element | Animation | Duration |
|---------|-----------|----------|
| Page load | Fade in | 200ms |
| Card expand | Height transition + fade | 300ms ease-out |
| Status change | Color transition | 200ms |
| Toast notification | Slide in from right + fade | 300ms |
| Modal open | Scale from 0.95 + fade | 200ms |
| Tab switch | Content fade | 150ms |
| Queue progress | Width transition | 1s linear |

### 6.2 Loading States

| Component | Loading State |
|-----------|--------------|
| Dashboard cards | Skeleton pulse animation |
| Video thumbnail | Blur placeholder + spinner |
| Data tables | Row skeletons (5 rows) |
| Charts | Skeleton chart shape |
| Buttons | Spinner icon + disabled state |
| Forms | Field-level skeletons |

### 6.3 Error States

| Component | Error State |
|-----------|-------------|
| API failure | Toast notification + retry button |
| Image load fail | Fallback placeholder icon |
| Empty state | Illustration + helpful message |
| Permission denied | Lock icon + contact admin message |

---

## 7. Telegram UI (Bot Interface)

### 7.1 Approval Notification

```
┌────────────────────────────────────────┐
│ YTAgent Bot                            │
├────────────────────────────────────────┤
│                                        │
│ 🎵 Lofi Chill                          │
│                                        │
│ "Relaxing Lofi Beats for Study         │
│  | 3 Hours" (Draft)                    │
│                                        │
│ 📅 Jadwal: 10:00 WIB                   │
│ 🎯 Confidence: 87%                     │
│                                        │
│ [✅ Approve] [✏️ Edit] [🗑️ Discard]    │
│                                        │
└────────────────────────────────────────┘
```

### 7.2 Daily Report (08:00 WIB)

```
┌────────────────────────────────────────┐
│ YTAgent Bot                            │
├────────────────────────────────────────┤
│                                        │
│ 📊 Laporan Harian — 26 Juni 2025       │
│                                        │
│ 📈 Performa Channel:                   │
│ • Lofi Chill: 1,245 views (↑15%)       │
│ • Oud Jazz: 892 views (↑8%)            │
│ • Ambient: 456 views (↓3%)             │
│                                        │
│ 🚨 Perlu Perhatian:                    │
│ • "Focus Music" CTR rendah (1.8%)      │
│   Thumbnail kurang kontras             │
│                                        │
│ ✅ Upload Hari Ini: 3 video            │
│ ⏳ Menunggu Approval: 2 video          │
│                                        │
│ [📊 Detail] [⚙️ Dashboard]             │
│                                        │
└────────────────────────────────────────┘
```

### 7.3 Anomaly Alert

```
┌────────────────────────────────────────┐
│ YTAgent Bot                            │
├────────────────────────────────────────┤
│                                        │
│ 🚨 ALERT — Lofi Chill                  │
│                                        │
│ Video "Focus Music" performa di        │
│ bawah rata-rata:                       │
│                                        │
│ • CTR: 1.8% (rata-rata: 3.2%)          │
│ • AVD: 2m 10s (rata-rata: 4m 32s)      │
│ • Views 24h: 87 (target: >100)         │
│                                        │
│ 💡 Saran:                              │
│ Thumbnail kurang kontras. Coba ganti   │
│ ke style "high-contrast" untuk video   │
│ berikutnya.                            │
│                                        │
│ [👍 Mengerti] [📊 Lihat Detail]        │
│                                        │
└────────────────────────────────────────┘
```

### 7.4 Upload Complete Confirmation

```
┌────────────────────────────────────────┐
│ YTAgent Bot                            │
├────────────────────────────────────────┤
│                                        │
│ ✅ Upload Selesai!                     │
│                                        │
│ 🎵 Lofi Chill                          │
│ "Relaxing Lofi Beats for Study         │
│  | 3 Hours"                            │
│                                        │
│ 🔗 youtube.com/watch?v=AbC123          │
│                                        │
│ 📊 Analytics akan tersedia dalam:      │
│ • 24 jam                               │
│ • 72 jam                               │
│                                        │
└────────────────────────────────────────┘
```

---

## 8. Form Validation

### 8.1 Channel Settings Form

| Field | Validation | Error Message |
|-------|-----------|---------------|
| Channel Name | Required, 3–128 chars | "Nama channel wajib diisi" |
| Folder Path | Must exist on OMV | "Folder tidak ditemukan di OMV" |
| Preferred Time | Valid time format | "Format waktu tidak valid" |
| Title Template | Max 256 chars | "Template terlalu panjang" |
| Tags | Max 15 tags, 30 chars each | "Maksimal 15 tag, 30 karakter per tag" |
| GCP Project ID | Required for active channels | "Project ID wajib untuk channel aktif" |

### 8.2 Video Metadata Form (Edit)

| Field | Validation | Error Message |
|-------|-----------|---------------|
| Title | Required, max 100 chars | "Judul wajib diisi, maksimal 100 karakter" |
| Description | Max 5000 chars | "Deskripsi terlalu panjang" |
| Tags | Max 15 tags, 500 chars total | "Tag terlalu banyak/terlalu panjang" |

---

## 9. Accessibility

### 9.1 Requirements

| Feature | Implementation |
|---------|---------------|
| Keyboard Navigation | All interactive elements focusable, Tab order logical |
| Screen Reader | ARIA labels on all icons, buttons, and form fields |
| Color Contrast | Minimum 4.5:1 for text, 3:1 for UI elements |
| Focus Indicators | Visible focus ring (2px blue outline) |
| Reduced Motion | `prefers-reduced-motion` support |
| Alt Text | All thumbnails have descriptive alt text |

### 9.2 ARIA Patterns

| Component | ARIA Pattern |
|-----------|-------------|
| Channel Selector | `role="listbox"`, `aria-expanded` |
| Video Cards | `role="article"`, `aria-label` with title |
| Queue List | `role="list"`, `aria-live="polite"` for updates |
| Status Badges | `role="status"` |
| Tabs | `role="tablist"`, `role="tab"`, `role="tabpanel"` |
| Modal | `role="dialog"`, `aria-modal="true"`, focus trap |
