# Cold Email Outreach System

**Version:** 2.0.0  
**Last Updated:** 2025-01-03

---

**Production-grade outreach infrastructure** designed to convert noisy, scraped data into campaign-safe leads and execute fault-tolerant, multi-stage email campaigns at scale.

Built to solve a core problem in outbound systems:
> *Scraped data is not outreach-ready.*

This system enforces strict normalization, deterministic scoring, and immutable campaign state before a single email is sent.

---

## Design at Scale

| Constraint | Solution |
| :--- | :--- |
| **~18,500 heterogeneous leads** | Independent pipelines per domain (academic/corporate) |
| **Zero state corruption** | Atomic CSV saves after every email |
| **Resumable execution** | Immutable campaign state with timestamp tracking |
| **Multi-stage campaigns** | Enforced follow-up windows (6-8 days) with stage isolation |

**Validated on:**
- 4,084 professors from 16 top universities (MIT, Stanford, Harvard, etc.)
- 14,400+ corporate executives (CEOs, VPs, Engineering Managers)
- 100% data recovery rate during SMTP failures

---

## System Architecture

```
Raw Data Sources
  (LinkedIn / Faculty / CSV/PDF)
        ↓
┌───────────────────────────────┐
│  Normalization Layer          │
│  • Hard filters (invalid)      │
│  • Role qualification          │
│  • Title normalization         │
│  • Email confidence scoring    │
└───────────────────────────────┘
        ↓
Qualified Lead Store
  (Immutable campaign schema)
        ↓
┌───────────────────────────────┐
│  Campaign Engine              │
│  • Template selection          │
│  • Daily quota management      │
│  • Multi-stage follow-ups      │
│  • Atomic state persistence    │
└───────────────────────────────┘
        ↓
SMTP Delivery
```

---

## Core Capabilities

### Data Integrity First
- **Strict normalization layer** separating scraping from outreach
- **Hard filters** for invalid profiles and non-decision roles
- **Canonical role mapping** with rejection diagnostics
- **Email confidence scoring** (0.3 minimum threshold)

### Deterministic Lead Qualification
- **Explainable HiringScore** (0–100), no LLM dependency
- **DNS MX verification** to prevent bounce-heavy domains
- **Confidence-scored email generation** (format confirmed → inferred → fallback)
- **Role-based filtering** (explicit allow/deny lists)

### Fault-Tolerant Campaign Execution
- **Atomic state persistence** after every email (temp file + `os.replace()`)
- **Multi-stage campaigns** with enforced follow-up windows
- **Daily send quotas** with test mode safeguards (450/day default)
- **SMTP retry logic** with connection recovery

### Scalable by Design
- **University- and company-isolated pipelines** (no cross-contamination)
- **No shared mutable state** across runs
- **Safe re-runs** and crash recovery
- **Organized diagnostics** per company/university

---

## Quick Start

```bash
# Process raw data
python scripts/data_cleaner.py

# Run campaign
python -m outreach.campaign
```

**Detailed workflows** for scraping, enrichment, and testing live in [docs/](docs/).

---

## Runtime Controls

### Campaign Configuration
Edit `outreach/config.py`:
- `CAMPAIGN_STAGE`: `'INITIAL_SEND'`, `'FOLLOW_UP_1'`, or `'FOLLOW_UP_2'`
- `DAILY_SEND_LIMIT`: Maximum emails per day (default: 450)
- `TEST_MODE`: Set to `True` for testing (sends only 5 emails)

### Environment Variables
See [docs/ENV_SETUP_GUIDE.md](docs/ENV_SETUP_GUIDE.md) for complete setup.

Required:
- `SENDER_EMAIL` - Gmail address
- `SENDER_PASSWORD` - Gmail App Password
- `LINKEDIN_EMAIL` - LinkedIn login (for scraping)
- `LINKEDIN_PASSWORD` - LinkedIn password

---

## Project Structure

```
coldemail/
├── outreach/                    # Campaign engine
│   ├── campaign.py             # Orchestration (atomic saves, quotas)
│   ├── config.py                # Configuration
│   ├── filters.py               # Stage-based filtering
│   ├── mailer.py                # SMTP with retry logic
│   └── templates.py             # Template selection
├── scraper_bridge/              # LinkedIn ingestion
│   ├── staffspy_ingest.py       # Main pipeline
│   ├── normalize_for_outreach.py # Normalization layer
│   └── diagnostics/             # Company-specific outputs
├── faculty-scraper/             # University faculty scraper
│   ├── professor_enrichment/    # Research enrichment (optional)
│   └── html_extractors/         # University-specific extractors
├── data/
│   ├── raw/                     # Input data
│   ├── processed/               # Master database
│   └── backups/                 # Backup files
├── scripts/                     # Root-level scripts
├── logs/                        # Execution logs
└── config/                      # Configuration files
```

---

## Non-Goals

This system intentionally does **not**:
- Use LLMs for scoring or filtering (determinism > novelty)
- Auto-send emails without persisted campaign state
- Optimize for UI-first usage over reliability
- Replace CRMs or inbox management tools
- Handle email replies or two-way communication

It is designed to be **predictable, auditable, and safe to re-run**.

---

## Operational Guarantees

- **Zero data loss**: Atomic CSV saves prevent corruption
- **Resumable execution**: Campaign state persists after crashes
- **No duplicate sends**: Email-based deduplication with timestamp tracking
- **Quota enforcement**: Daily limits prevent account suspension
- **Isolated pipelines**: University/company data processed independently

---

## Documentation

- [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) - Detailed architecture
- [docs/CODEBASE_OVERVIEW.md](docs/CODEBASE_OVERVIEW.md) - File-by-file breakdown
- [docs/NORMALIZATION_ARCHITECTURE.md](scraper_bridge/NORMALIZATION_ARCHITECTURE.md) - Normalization layer design
- [docs/CHANGELOG.md](docs/CHANGELOG.md) - Version history
- [docs/VERSIONING.md](docs/VERSIONING.md) - Documentation versioning guide

---

## Installation

```bash
# Clone and setup
git clone <repo-url>
cd coldemail
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

**Prerequisites:**
- Python 3.8+
- Ruby (for faculty scraper scripts)
- Gmail account with App Password
- LinkedIn account (for scraping)

---

## Security

- **Never commit `.env` file** - Contains sensitive credentials
- Use Gmail App Passwords (not regular passwords)
- Review `.gitignore` to ensure sensitive files are excluded
- Rotate credentials periodically

---

## Prior Art

- Faculty scraper based on [barc-iitkgp/faculty-scraper](https://github.com/barc-iitkgp/faculty-scraper)

---

## Why This Exists

Most outbound systems fail silently due to poor data quality and fragile state.

This project treats outreach as a **data and state management problem**, not a copywriting problem. The normalization layer enforces strict data contracts that scrapers don't provide, and the campaign engine guarantees immutable state that survives crashes, network failures, and manual interruptions.

---

## License

[Add your license here]
