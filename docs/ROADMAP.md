# ROADMAP.md

## YTAgent — Implementation Roadmap

> **Version:** 1.0.0
> **Date:** 2025-06-26
> **Status:** Planning
> **Goal:** MVP within 4–6 weeks, full system within 10–12 weeks

---

## 1. Roadmap Overview

```
Phase 0 (Week 0)    Phase 1 (Weeks 1-2)   Phase 2 (Weeks 3-4)   Phase 3 (Weeks 5-6)
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Environment    │  │  Core Pipeline  │  │  Dashboard +    │  │  Polish +       │
│  Setup          │  │  (Detection →   │  │  Telegram       │  │  Integration    │
│                 │  │   Upload)       │  │  Integration    │  │  Testing        │
└─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘
        │                     │                     │                     │
        ▼                     ▼                     ▼                     ▼
   VM Preparation      File Watcher         React Dashboard      End-to-End
   Docker Compose      + Screenshot         + Telegram Bot       Testing
   MySQL/Redis/Qdrant  + AI Generation      + Queue Manager      Bug Fixes
   Project Scaffold    + YouTube Upload     + Staging Area       Performance
   Basic Auth          + Celery Queue       + Basic Analytics    Optimization


Phase 4 (Weeks 7-8)   Phase 5 (Weeks 9-10)  Phase 6 (Weeks 11-12)
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Analytics +    │  │  AI Insights +  │  │  Optimization + │
│  Qdrant         │  │  A/B Testing    │  │  Full Launch    │
│                 │  │                 │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
   YouTube Analytics    Pattern Recognition    Auto-Approve Mode
   Data Collection     + Insight Generation   + GCP Manager
   Qdrant Integration  + A/B Test Framework   + Bulk Operations
   08:00 Reports       + Metadata Versioning  + Documentation
   Anomaly Detection   + Advanced Alerts      + Training Video
```

---

## 2. Phase 0: Environment Setup (Week 0)

**Goal:** Prepare the infrastructure so development can begin immediately.

| Task | Description | Deliverable | Est. Time |
|------|-------------|-------------|-----------|
| **0.1** | Configure OMV shared folders | `/shared/videos/[channel]/` accessible from Ubuntu VM | 2h |
| **0.2** | Mount OMV to Ubuntu VM | SMB/CIFS mount at `/mnt/omv/`, fstab entry | 2h |
| **0.3** | Install Docker & Docker Compose | Docker 24+, Compose 2.20+ | 1h |
| **0.4** | Scaffold project structure | All directories from FILE_STRUCTURE.md created | 1h |
| **0.5** | Create base Docker Compose | MySQL 8, Redis, Qdrant containers running | 2h |
| **0.6** | Setup Python environment | Python 3.11, virtual env, base dependencies | 1h |
| **0.7** | Setup React environment | Vite + React 18 + Tailwind + shadcn/ui | 2h |
| **0.8** | Create Alembic setup | Initial migration, database creation | 1h |
| **0.9** | Setup Git repository | `.gitignore`, initial commit, branch protection | 1h |
| **0.10** | Document environment | README with setup instructions | 2h |
| **0.11** | **Setup automated backup** | `mysqldump` cron daily → syncs to `/mnt/omv/backups/`. **Do NOT defer to Week 12.** | 2h |

> ⚠️ **Backup is Phase 0, not Phase 6.** The system is production-ready at the end of Phase 3 (Week 6). A MySQL crash before Week 12 without backups means total data loss. Backup must be operational before any real channel data is stored.

**Total:** ~17 hours (2–3 days)

**Backup Script (Phase 0 deliverable):**
```bash
# scripts/backup-db.sh — runs via crontab daily at 03:00 WIB
#!/bin/bash
BACKUP_DIR="/mnt/omv/backups/mysql"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"
docker compose exec -T mysql mysqldump \
  -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" ytagent \
  | gzip > "$BACKUP_DIR/ytagent_$TIMESTAMP.sql.gz"
# Keep only last 14 days
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +14 -delete
echo "Backup complete: ytagent_$TIMESTAMP.sql.gz"
```

**Dependencies:** None

---

## 3. Phase 1: Core Pipeline — "Detect to Upload" (Weeks 1–2)

**Goal:** Build the complete backend pipeline from file detection to YouTube upload.

### Week 1: Detection & Preparation

| Task | Description | Deliverable | Est. Time |
|------|-------------|-------------|-----------|
| **1.1** | Implement File Watcher service | `watchdog` detecting new files in OMV folders | 6h |
| **1.2** | File completion detection | Size stability check (5 seconds) | 3h |
| **1.3** | ffmpeg screenshot extraction | Frame at second 30, save as JPG | 4h |
| **1.4** | Channel model & CRUD | Database schema, API endpoints | 4h |
| **1.5** | Video model & lifecycle | Status machine, CRUD operations | 4h |
| **1.6** | Thumbnail generation service | Cloudflare AI integration, 3 options + PIL fallback | 6h |
| **1.7** | Metadata generation service | Title, description, tag generation | 6h |
| **1.8** | **Sync SQLAlchemy engine for Celery** | Add `sync_database_url` config, verify Celery tasks use sync Session | 2h |

**Week 1 Total:** ~41 hours

### Week 2: Upload & Queue

| Task | Description | Deliverable | Est. Time |
|------|-------------|-------------|-----------|
| **2.1** | YouTube OAuth manager | Token storage (channel_credentials table), refresh, per-channel | 6h |
| **2.2** | YouTube upload service | Resumable upload via Data API v3 | 6h |
| **2.3** | Celery setup | Redis broker, single worker, sync Session confirmed | 4h |
| **2.4** | Upload task implementation | Background upload with progress tracking | 6h |
| **2.5** | Retry logic | Exponential backoff, max 5 retries, jitter | 4h |
| **2.6** | Sequential queue guarantee | Single worker, task routing | 3h |
| **2.7** | Celery Beat scheduler | Periodic task framework + GCP quota reset task + log rotation task | 4h |
| **2.8** | GCP quota auto-rotation | Auto-switch project on quota exceeded | 4h |
| **2.9** | Basic health endpoints | `/health`, service status | 2h |

**Week 2 Total:** ~39 hours

**Phase 1 Milestone:**
- ✅ Copy file to OMV → Auto-detected → Screenshot → AI thumbnail + metadata → Manual approval (API) → Upload to YouTube
- ✅ Queue is strictly sequential
- ✅ Retry logic works for transient failures

**Dependencies:** Phase 0 complete

---

## 4. Phase 2: Dashboard + Telegram (Weeks 3–4)

**Goal:** Build the user-facing interfaces for Supervisor interaction.

### Week 3: Dashboard Foundation

| Task | Description | Deliverable | Est. Time |
|------|-------------|-------------|-----------|
| **3.1** | Dashboard layout & navigation | Sidebar, header, channel selector | 6h |
| **3.2** | Global Dashboard page | Health bar, channel grid, quick stats | 6h |
| **3.3** | Staging Area page | Video cards, approve/edit/discard actions | 8h |
| **3.4** | Video Detail page | Tabs: overview, metadata, thumbnails | 6h |
| **3.5** | Metadata editor form | Title, description, tags with validation | 4h |
| **3.6** | Thumbnail carousel | Select from 3 AI-generated options | 4h |
| **3.7** | API integration layer | TanStack Query setup, all endpoints | 6h |

**Week 3 Total:** ~40 hours

### Week 4: Telegram + Queue Manager

| Task | Description | Deliverable | Est. Time |
|------|-------------|-------------|-----------|
| **4.1** | Telegram bot setup | Bot creation, webhook/polling configuration | 3h |
| **4.2** | Inline keyboard handlers | [Approve] [Edit] [Discard] buttons | 4h |
| **4.3** | Notification service | Send approval requests to Supervisor | 4h |
| **4.4** | Queue Manager page | Real-time queue status, active upload | 6h |
| **4.5** | Channel Settings page | Preset configuration, GCP credentials | 6h |
| **4.6** | Basic auth (JWT) | Login, token management | 4h |
| **4.7** | Logs page | Filterable system logs viewer | 4h |
| **4.8** | Error handling UI | Toast notifications, error states | 3h |

**Week 4 Total:** ~34 hours

**Phase 2 Milestone:**
- ✅ Supervisor receives Telegram notification with [Approve] [Edit] [Discard]
- ✅ [Approve] triggers upload without opening dashboard
- ✅ Dashboard shows staging area, queue, channel settings
- ✅ Editor copies file → everything else is automated

**Dependencies:** Phase 1 complete

---

## 5. Phase 3: Polish & Integration Testing (Weeks 5–6)

**Goal:** Ensure the MVP works end-to-end with real YouTube channels.

### Week 5: Integration & Real-World Testing

| Task | Description | Deliverable | Est. Time |
|------|-------------|-------------|-----------|
| **5.1** | Setup 2 test YouTube channels | Real GCP projects, OAuth flow | 4h |
| **5.2** | End-to-end pipeline test | Full flow with real YouTube uploads | 6h |
| **5.3** | OAuth token refresh automation | Auto-refresh before expiry | 4h |
| **5.4** | Upload progress tracking | Real-time progress in dashboard | 4h |
| **5.5** | Schedule override | Change upload time per video | 4h |
| **5.6** | Time-Override Management | Preferred time as guideline | 4h |
| **5.7** | File type validation | Only .mp4, .mov, .avi accepted | 2h |
| **5.8** | Storage monitoring | Alert at 80% OMV capacity | 3h |

**Week 5 Total:** ~31 hours

### Week 6: Safety & Error Handling

| Task | Description | Deliverable | Est. Time |
|------|-------------|-------------|-----------|
| **6.1** | Copyright claim detection | Check YouTube API for claims | 4h |
| **6.2** | Auto-pause all queues | STOP on copyright claim | 3h |
| **6.3** | Critical alert system | Immediate Telegram notification | 3h |
| **6.4** | Circuit breaker for APIs | Prevent cascading failures | 4h |
| **6.5** | Graceful shutdown | Finish current upload on stop signal | 3h |
| **6.6** | Database backup script | Automated daily backup | 3h |
| **6.7** | Logging audit | All significant events logged | 4h |
| **6.8** | Bug fixes & stabilization | Fix issues from testing | 8h |

**Week 6 Total:** ~32 hours

**Phase 3 Milestone (MVP COMPLETE):**
- ✅ 2 channels uploading automatically via Telegram approval
- ✅ Copyright safety working (auto-pause)
- ✅ Dashboard functional for all primary workflows
- ✅ System stable for daily use

**Dependencies:** Phase 2 complete

---

## 6. Phase 4: Analytics & Qdrant (Weeks 7–8)

**Goal:** Add performance tracking and the feedback loop.

### Week 7: Analytics Collection

| Task | Description | Deliverable | Est. Time |
|------|-------------|-------------|-----------|
| **7.1** | YouTube Analytics API integration | Query views, CTR, AVD | 6h |
| **7.2** | Analytics data collection task | Celery task: collect at 24h and 72h | 4h |
| **7.3** | Analytics database schema | analytics_records table | 3h |
| **7.4** | Analytics API endpoints | Dashboard data endpoints | 4h |
| **7.5** | Dashboard analytics page | Charts, graphs, performance tables | 8h |
| **7.6** | Recharts integration | Views trend, CTR, AVD charts | 4h |
| **7.7** | Performance data table | Sortable, filterable video list | 4h |

**Week 7 Total:** ~33 hours

### Week 8: Qdrant & Reports

| Task | Description | Deliverable | Est. Time |
|------|-------------|-------------|-----------|
| **8.1** | Qdrant collection setup | video_performance, title_embeddings | 4h |
| **8.2** | Text embedding generation | Sentence transformer for titles | 4h |
| **8.3** | Store performance vectors | Upsert after analytics collection | 4h |
| **8.4** | Similarity search | Find similar performing videos | 4h |
| **8.5** | 08:00 WIB report generation | Accumulative daily report | 6h |
| **8.6** | Telegram report delivery | Daily report via Telegram | 3h |
| **8.7** | Anomaly detection | CTR < 2%, views < 100, AVD drop | 6h |
| **8.8** | Anomaly alerts | Immediate Telegram alert | 3h |

**Week 8 Total:** ~34 hours

**Phase 4 Milestone:**
- ✅ Analytics collected automatically at 24h and 72h
- ✅ Daily report sent at 08:00 WIB
- ✅ Qdrant stores performance patterns
- ✅ Anomaly detection alerts Supervisor

**Dependencies:** Phase 3 complete

---

## 7. Phase 5: AI Insights & A/B Testing (Weeks 9–10)

**Goal:** Enable the AI to provide actionable insights and support experimentation.

### Week 9: AI Insights

| Task | Description | Deliverable | Est. Time |
|------|-------------|-------------|-----------|
| **9.1** | Pattern recognition service | Compare video vs. channel average | 6h |
| **9.2** | Insight generation engine | Generate actionable messages | 6h |
| **9.3** | Qdrant similarity for suggestions | "Videos like this that performed well" | 6h |
| **9.4** | Insight API endpoints | List, dismiss, apply insights | 4h |
| **9.5** | Insight cards in dashboard | Display AI suggestions | 4h |
| **9.6** | Insight notification via Telegram | Send insights as they occur | 3h |
| **9.7** | Confidence scoring | Score metadata drafts 0-100% | 4h |

**Week 9 Total:** ~33 hours

### Week 10: A/B Testing & Metadata Versioning

| Task | Description | Deliverable | Est. Time |
|------|-------------|-------------|-----------|
| **10.1** | Metadata versioning | Save each draft version | 4h |
| **10.2** | Version history UI | View past versions, compare | 4h |
| **10.3** | A/B test marking | Tag videos with test groups | 4h |
| **10.4** | A/B test results comparison | Compare performance after 72h | 4h |
| **10.5** | AI quality score | Rate metadata 1-10 | 3h |
| **10.6** | Auto-approve mode | Per-channel toggle | 4h |
| **10.7** | Confidence threshold | Auto-approve if score >= 80% | 3h |
| **10.8** | Metadata experiment UI | Create, track, apply experiments | 6h |

**Week 10 Total:** ~32 hours

**Phase 5 Milestone:**
- ✅ AI provides actionable insights ("CTR rendah, coba style X")
- ✅ A/B testing tracks title/thumbnail variants
- ✅ Auto-approve mode works with confidence threshold
- ✅ Metadata versioning preserves history

**Dependencies:** Phase 4 complete

---

## 8. Phase 6: Optimization & Launch (Weeks 11–12)

**Goal:** Scale to full channel count, optimize, and document.

### Week 11: Scale & Optimize

| Task | Description | Deliverable | Est. Time |
|------|-------------|-------------|-----------|
| **11.1** | GCP Quota Manager | Dashboard showing quota per project | 4h |
| **11.2** | Multi-GCP project support | Seamless switching on quota exceed | 4h |
| **11.3** | Add remaining channels | Onboard all 10–30 channels | 6h |
| **11.4** | Performance optimization | Query optimization, caching | 6h |
| **11.5** | Bulk operations | Bulk approve, bulk edit | 4h |
| **11.6** | Mobile responsiveness polish | All pages mobile-friendly | 4h |
| **11.7** | Dark/light mode toggle | Theme switching | 3h |
| **11.8** | Onboarding flow | First-time setup wizard | 4h |

**Week 11 Total:** ~35 hours

### Week 12: Documentation & Training

| Task | Description | Deliverable | Est. Time |
|------|-------------|-------------|-----------|
| **12.1** | User manual (Supervisor) | How to use Telegram + Dashboard | 4h |
| **12.2** | User manual (Editor) | How to render and copy to OMV | 2h |
| **12.3** | API documentation | OpenAPI/Swagger docs complete | 3h |
| **12.4** | Troubleshooting guide | Common issues and solutions | 3h |
| **12.5** | System architecture diagram | Visual architecture docs | 2h |
| **12.6** | ~~Backup & recovery guide~~ | ~~Database backup script~~ | ~~Moved to Phase 0~~ |
| **12.6** | Backup & recovery guide | Verify backup integrity, document restore procedure | 2h |
| **12.7** | Final bug fixes | Address any remaining issues | 8h |
| **12.8** | System hardening | Security review, penetration test | 4h |
| **12.9** | Training session | Walkthrough with Supervisor | 2h |

**Week 12 Total:** ~30 hours

**Phase 6 Milestone (FULL LAUNCH):**
- ✅ All 10–30 channels active
- ✅ Supervisor fully trained
- ✅ System documentation complete
- ✅ Backup & recovery tested

**Dependencies:** Phase 5 complete

---

## 9. Summary Timeline

| Phase | Duration | Focus | Key Deliverable |
|-------|----------|-------|-----------------|
| **0** | Week 0 | Environment | Running Docker stack |
| **1** | Weeks 1–2 | Core Pipeline | File → YouTube upload works |
| **2** | Weeks 3–4 | UI + Telegram | Supervisor can approve via Telegram |
| **3** | Weeks 5–6 | Polish + Safety | MVP ready with 2 channels |
| **4** | Weeks 7–8 | Analytics | Daily reports, anomaly detection |
| **5** | Weeks 9–10 | AI Insights | Smart suggestions, A/B testing |
| **6** | Weeks 11–12 | Scale + Launch | All channels, full documentation |

**Total Duration:** 12 weeks (3 months)
**Total Effort:** ~380 hours

---

## 10. Risk Mitigation

| Risk | Impact | Mitigation | Contingency |
|------|--------|-----------|-------------|
| YouTube API quota limits | High | Multiple GCP projects + **auto-rotation built in Phase 1** | Prioritize active channels, rotate uploads |
| Cloudflare AI API unstable | Medium | **PIL-based text overlay fallback** (local, no external dependency) | Screenshot is always last resort |
| OMV network issues | High | Robust file watcher with retries | Manual scan button, health alerts |
| OAuth token expiry | Medium | Auto-refresh mechanism (via channel_credentials table) | Manual refresh via dashboard |
| Copyright claim (false positive) | High | Auto-pause all queues | Manual review + resume |
| Supervisor learning curve | Low | Minimalist Telegram UI | Training session, simple dashboard |
| VM resource constraints | Medium | Monitor resource usage | Scale VM resources (add RAM/CPU) |
| **Data loss on VM crash** | **High** | **Automated daily backup to OMV (Phase 0)** | Restore from latest backup |
| **asyncio+Celery conflict** | **High** | **Sync Session in all Celery tasks (enforced in code review)** | N/A — prevented by standard |
| **system_logs table growth** | Medium | Weekly log rotation Celery task | MySQL partitioning if needed |

---

## 11. Post-Launch Roadmap (Future)

| Feature | Priority | Description |
|---------|----------|-------------|
| **Public/Scheduled Publishing** | P1 | Upload as private, schedule public release |
| **Bulk Upload (Sequential)** | P1 | Queue multiple videos efficiently |
| **Comment Management** | P2 | Monitor and reply to comments |
| **Community Posts** | P2 | Schedule community posts |
| **Multi-Language Metadata** | P2 | Generate metadata in multiple languages |
| **Advanced Analytics** | P2 | Retention graphs, traffic source analysis |
| **Competitor Analysis** | P3 | Track competitor channel performance |
| **Content Calendar** | P3 | Plan content weeks in advance |
| **Mobile App** | P3 | React Native app for mobile supervision |
| **Cross-Platform** | P3 | TikTok, Instagram integration |
