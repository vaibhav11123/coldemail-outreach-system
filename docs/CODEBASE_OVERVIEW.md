# Complete Codebase Overview

**Version:** 2.0.0  
**Last Updated:** 2025-01-03  
**Changelog:**
- v2.0.0: Updated for new file structure, normalization layer, campaign improvements, path updates
- v1.0.0: Initial version

---

This document provides a comprehensive understanding of every code file in the cold email outreach system.

---

## Architecture Overview

The system consists of four main modules:

1. **Data Collection & Processing** (`scripts/data_cleaner.py`)
2. **LinkedIn Scraping & Normalization** (`scraper_bridge/`) - **NEW: Normalization Layer**
3. **Faculty Profile Enrichment** (`faculty-scraper/professor_enrichment/`)
4. **Email Campaign Engine** (`outreach/`) - **IMPROVED: Atomic Saves, Quota Management**

---

## 1. Root Level: Data Processing

### `scripts/data_cleaner.py`

**Purpose:** Processes raw CSV and PDF files containing HR contact data, cleans and normalizes the data, and calculates hiring scores.

**Location:** Moved to `scripts/` directory for better organization.

**Path Configuration:** Uses relative paths from `scripts/` directory:
- Input files: `../data/raw/`
- Output file: `../data/processed/cold_email_outreach_all_cleaned_ranked.csv`

**Key Functions:**
- `clean_email()` - Removes invalid characters from emails
- `clean_text()`, `clean_name()`, `clean_title()`, `clean_company()` - Text normalization helpers
- `parse_hr_pdf()` - Extracts contact data from PDF tables using `pdfplumber`
- `process_csv()` - Processes CSV files, skips header rows, normalizes columns
- `hiring_score()` - Calculates 10-100 score based on job title keywords
- `main()` - Orchestrates CSV and PDF processing, deduplication, and output

**Data Flow:**
1. Reads CSV file (skips first 3 rows)
2. Reads PDF file (extracts tables)
3. Concatenates both DataFrames
4. Validates emails (regex pattern)
5. Calculates `HiringScore` for each row
6. Sorts by `HiringScore` (descending)
7. Removes duplicates (by Email + Company)
8. Outputs to `data/processed/cold_email_outreach_all_cleaned_ranked.csv`

**Test Mode:** Can limit CSV rows and PDF pages for testing

**Output Schema:**
- `Name`, `Title`, `Email`, `Company`, `Location`, `Source`, `HiringScore`

---

## 2. Outreach Module (`outreach/`)

### `campaign.py`

**Purpose:** Main orchestration script for email campaigns. Manages the entire email sending workflow with state persistence.

**Key Features:**
- **Path Resolution:** Uses `Path(__file__).parent.parent` to resolve project root, then joins with `config.FILE_TO_LOAD`
- **File Location:** Loads from `data/processed/cold_email_outreach_all_cleaned_ranked.csv`
- **Atomic CSV Saves:** Uses `save_campaign_state()` function with temporary files and `os.replace()` for fault-tolerant saves
- **Daily Quota Management:** Tracks emails sent today per campaign stage, enforces 450/day limit
- **State Persistence:** Saves CSV after each successful email send (not batch) for maximum fault tolerance
- **Campaign Stage Support:** Handles INITIAL_SEND, FOLLOW_UP_1, FOLLOW_UP_2 with stage-specific timestamp columns
- **SMTP Connection Management:** Establishes connection once, reuses for all emails
- **Environment Loading:** Loads `.env` file BEFORE any imports to ensure credentials are available

**Workflow:**
1. Loads `.env` file (critical: must happen before imports)
2. Sets up logging via `config.setup_logging()`
3. Loads master CSV file
4. Initializes tracking columns if missing
5. Checks daily quota (counts emails sent today for current stage)
6. Filters recipients using `filter_recipients_by_stage()`
7. Applies test mode limit or daily quota limit
8. Establishes SMTP connection
9. **Send Loop:**
   - Selects template based on score/title
   - Formats email with personalization
   - Sends via `SMTPMailer`
   - Updates status and timestamp
   - **Saves CSV immediately after success** (atomic save)
   - Random delay (5-15 seconds)
10. Final cleanup and save

**Critical Design Decisions:**
- Saves after each email (not batch) for maximum fault tolerance
- Uses temporary file + atomic replace for safe saves
- Handles both module import and direct execution

### `config.py`

**Purpose:** Centralized configuration for the outreach module.

**Configuration:**
- `SENDER_EMAIL`, `SENDER_PASSWORD` - From `.env` file
- `SMTP_SERVER`, `SMTP_PORT` - Gmail SMTP settings
- `FILE_TO_LOAD` - Master CSV path: `"data/processed/cold_email_outreach_all_cleaned_ranked.csv"`
- `LOG_FILE` - Log output path: `"logs/outreach_campaign.log"`
- `DAILY_SEND_LIMIT` - 450 emails/day default
- `CAMPAIGN_STAGE` - 'INITIAL_SEND', 'FOLLOW_UP_1', or 'FOLLOW_UP_2'
- `TEST_MODE` - Boolean flag
- `MAX_EMAILS_IN_TEST` - 5 emails in test mode

**Functions:**
- `setup_logging()` - Initializes logging, validates `SENDER_PASSWORD`

### `filters.py`

**Purpose:** Filters contacts based on campaign stage and time windows.

**Key Function:**
- `filter_recipients_by_stage(df)` - Returns filtered DataFrame based on `config.CAMPAIGN_STAGE`

**Filtering Logic:**

1. **INITIAL_SEND:**
   - Returns all rows where `Sent_Status == 'PENDING'`

2. **FOLLOW_UP_1:**
   - Requires: `Sent_Status == 'SENT_SUCCESS'`
   - Requires: `FollowUp_1_Status` not in `['SENT_SUCCESS', 'FAILED_REFUSED']`
   - Time window: 6-8 days after `Sent_Timestamp`

3. **FOLLOW_UP_2:**
   - Requires: `Sent_Status == 'SENT_SUCCESS'`
   - Requires: `FollowUp_1_Status == 'SENT_SUCCESS'`
   - Requires: `FollowUp_2_Status` not in `['SENT_SUCCESS', 'FAILED_REFUSED']`
   - Time window: 6-8 days after `FollowUp_1_Timestamp`

**Edge Cases:**
- Initializes missing tracking columns
- Handles invalid timestamps gracefully (coerce to NaT, dropna)

### `mailer.py`

**Purpose:** Manages SMTP connection lifecycle and email sending with retry logic.

**Class: `SMTPMailer`**

**Methods:**
- `__init__()` - Initializes connection state
- `connect()` - Establishes SMTP connection with TLS
  - Handles stale connections (quits first if exists)
  - 30-second timeout
  - Returns `True` on success, `False` on failure
- `disconnect()` - Safely closes connection
  - Handles `SMTPServerDisconnected` gracefully
- `send_email()` - Sends single email with retry logic
  - Checks connection before send
  - Reconnects if connection lost
  - Retry logic: 1 retry attempt on `SMTPServerDisconnected`
  - Returns: `"SUCCESS"`, `"FAILED_REFUSED"`, or `"FAILED_OTHER"`

**Error Handling:**
- `SMTPRecipientsRefused` → `"FAILED_REFUSED"` (bad email)
- `SMTPServerDisconnected` → Reconnect and retry once
- Other exceptions → `"FAILED_OTHER"`

### `templates.py`

**Purpose:** Email template management and selection logic.

**Templates:**
- `TEMPLATE_1` - Primary cold email (high-score leads, 90-100)
- `TEMPLATE_2` - Ultra-short version (score < 90)
- `TEMPLATE_3` - ML-focused version (tech-leaning leaders)
- `TEMPLATE_4` - First follow-up (6-7 days)
- `TEMPLATE_5` - Second follow-up (12-14 days, final)

**Functions:**
- `get_salutation_name(name)` - Extracts first name, falls back to "Hiring Team"
- `get_initial_template(score, title)` - Template selection logic:
  1. Tech titles (CTO, Head of AI, etc.) → `TEMPLATE_3`
  2. High score (≥90) → `TEMPLATE_1`
  3. Default → `TEMPLATE_2`

**Template Variables:**
- `{FirstName}` - First name
- `{Company}` - Company name

---

## 3. Scraper Bridge Module (`scraper_bridge/`)

### `staffspy_ingest.py`

**Purpose:** Main pipeline for scraping LinkedIn profiles using StaffSpy, normalizing data, scoring, and staging leads.

**Key Components:**

1. **Configuration:**
   - `SAFE_SINGLE_COMPANY_MODE` - Test mode (single company)
   - `PRODUCTION_MODE` - Full production run
   - `DIAGNOSTICS_BASE_DIR` - Organized output directory structure
   - `TARGET_TITLES` - List of target job titles (normalized to lowercase)

2. **Helper Functions:**
   - `extract_primary_email()` - Parses stringified email lists
   - `safe_int()`, `safe_bool()` - Safe pandas NA handling
   - `staffspy_hiring_score()` - Calculates 0-100 score based on title, skills, experience, followers, hiring status
   - `load_target_companies()` - Loads companies from CSV
   - `update_target_companies_file()` - Saves remaining companies (production resume)
   - `filter_invalid_profiles()` - Legacy hard filter (now handled by normalization)
   - `apply_outreach_quality_filters()` - Legacy filter (now handled by normalization)
   - `data_audit()` - Final data quality checks
   - `generate_email_from_pattern()` - Legacy email generation

3. **Main Pipeline (`scrape_and_stage_new_leads`):**
   - Initializes LinkedInAccount with credentials
   - Loads target companies (filtered in SAFE mode)
   - **Per-company loop:**
     - Creates company-specific diagnostics directory
     - Scrapes with StaffSpy (`account.scrape_staff()`)
     - Saves raw snapshot
     - **Calls normalization layer** (`normalize_for_outreach()`)
     - Saves normalized outputs (outreach-ready, rejected debug)
     - Converts normalized schema to legacy format for scoring
     - Preserves raw fields (followers, connections, skills) for scoring
   - Post-processing:
     - Email validation
     - Deduplication against master CSV
     - Data audit
     - HiringScore calculation
     - Confidence mapping (1/2/3)
     - Campaign state initialization
   - Saves to staging CSV (production) or test snapshot (safe mode)

**Directory Structure:**
```
scraper_bridge/
├── diagnostics/
│   └── company_snapshots/
│       └── {company_name}/
│           ├── staffspy_raw_snapshot.csv
│           ├── staffspy_outreach_ready.csv
│           └── staffspy_rejected_debug.csv
└── staffspy_new_leads_staging.csv
```

### `normalize_for_outreach.py`

**Purpose:** Transforms raw StaffSpy scraping output into outreach-ready data with strict data contracts.

**See `NORMALIZATION_ARCHITECTURE.md` for detailed documentation.**

**Key Functions:**
- `hard_filter_invalid_profiles()` - Removes structurally unrecoverable rows
- `filter_by_role_relevance()` - Applies explicit allow/deny lists
- `normalize_role()` - Maps noisy titles to canonical roles
- `generate_email_with_confidence()` - Priority-based email generation
- `normalize_for_outreach()` - Main orchestration function

---

## 4. Faculty Scraper Module (`faculty-scraper/professor_enrichment/`)

### `run_enrichment.py`

**Purpose:** Main orchestration script for enriching faculty profiles with research information.

**Key Features:**
- **Multi-CSV Support:** Scans `data/` directory, allows user to select which universities to process
- **Independent Processing:** Each CSV processed separately (no cross-contamination)
- **Harvard URL Generation:** Auto-generates Harvard profile URLs from names if missing
- **Skip/Rerun Logic:** Asks user if they want to re-run already-scraped profiles
- **Periodic Saves:** Saves CSV every N rows (configurable)
- **Sent Status Logic:** Sets `Sent_Status` based on enrichment quality

**Workflow:**
1. Scans `data/` directory for CSV files
2. Prompts user to select universities (or "all")
3. **For each selected CSV:**
   - Loads CSV
   - Detects university type from CSV name
   - **Harvard-specific:** Generates missing profile URLs
   - Initializes enrichment columns
   - Checks for already-scraped profiles
   - Prompts for rerun confirmation
   - **Scraping loop:**
     - Calls `scrape_and_process_profile()` for each row
     - Updates DataFrame in-place
     - Periodic saves
     - Random delays
   - Sets `Sent_Status` based on `Scrape_Status` and `Confidence`
   - Final save and summary

**Helper Functions:**
- `safe_save_csv()` - Simple CSV save wrapper
- `ask_rerun_confirmation()` - User prompt for rerun
- `ask_csv_selection()` - Interactive university selection
- `detect_university_from_url()` - Detects university from URL
- `detect_university_from_csv_name()` - Detects university from CSV filename
- `generate_harvard_url_from_name()` - Generates Harvard SEAS URLs from names
- `ensure_harvard_profile_links()` - Fills missing Harvard URLs

### `scraper.py`

**Purpose:** Web scraping functions for fetching and extracting faculty profile content.

**Key Function:**
- `scrape_and_process_profile(row)` - Main scraping function

**Workflow:**
1. Validates URL from row
2. Normalizes http → https
3. **Berkeley fallback URLs:** Generates alternative URLs if main URL fails
4. **Retry Logic:** 3 attempts per URL with exponential backoff
5. Detects university type from URL
6. **University-aware extraction:**
   - Harvard → `extract_harvard_text()`
   - UCLA → `extract_ucla_research_text()`
   - Generic → `extract_generic_text()`
7. **NLP Processing:**
   - Extracts primary focus
   - Calculates confidence score
   - Infers research question
   - Builds personalization line
   - Generates subject line
   - Calculates hiring score
   - Infers domain
8. Returns structured result dictionary

**Error Handling:**
- Invalid URLs → Error response
- Connection timeouts → Retry with backoff
- All failures → Structured error response with details

### `nlp_processor.py`

**Purpose:** NLP processing and scoring functions for faculty research content.

**Key Functions:**

1. **Text Processing:**
   - `extract_sentences()` - Splits text into sentences (min 40 chars)
   - `score_sentence()` - Scores sentence based on AI/ML keyword density
   - `extract_primary_focus()` - Extracts best research sentence:
     - Filters out role/biographical sentences
     - Keeps sentences with research verbs
     - Ranks by keyword score
     - Cleans up common prefixes

2. **Scoring:**
   - `confidence_score()` - Calculates 0-3 confidence:
     - Signal 1: Length threshold (40 chars, 25 for Harvard)
     - Signal 2: Keyword density (≥2 keywords, ≥1 for Harvard)
     - Signal 3: Research verb presence
   - `calculate_hiring_score()` - Calculates 10-95 score:
     - Base: 10
     - +40: Reinforcement, foundation, robotics, representation, causal
     - +30: Deep learning, optimization, neural, computer vision, generative AI
     - +15: Machine learning, NLP, AI, data science
     - +10: Lab or center mentions

3. **Personalization:**
   - `build_personalization_line()` - Confidence-aware personalization:
     - Confidence 0: Generic fallback
     - Confidence 2: Medium detail
     - Confidence 3: High detail with research question
   - `generate_subject_line()` - Confidence-aware subject lines
   - `infer_research_question()` - Converts research statement to implicit question

4. **Domain Inference:**
   - `infer_domain()` - Categorizes research into domains:
     - Robotics / RL
     - Computer Vision
     - NLP / Language
     - Foundations / Theory
     - Data Science / Optimization
     - General ML

**Helper Functions:**
- `is_role_sentence()` - Detects biographical/role sentences
- `has_research_signal()` - Detects research activity verbs

### `config.py`

**Purpose:** Configuration for faculty enrichment module.

**Configuration:**
- `MODE` - 'TEST' or 'PROD'
- `LOG_DETAIL` - 0 (minimal), 1 (medium), 2 (full)
- `TEST_ROW_LIMIT` - 5 rows in test mode
- `SAVE_EVERY_N_ROWS` - Periodic save frequency
- `DATA_DIR` - Path to data directory (auto-detected)
- `BASE_SLEEP_TIME` - 1.5 seconds
- `REQUESTS_TIMEOUT` - 10 seconds
- `AI_KEYWORDS` - List of AI/ML keywords for scoring
- `BAD_SENTENCE_PATTERNS` - Patterns to filter out
- `RESEARCH_VERBS` - Verbs indicating research activity
- `HEADERS` - HTTP headers for scraping

### `utils/data_loader.py`

**Purpose:** Utility functions for loading data files.

**Functions:**
- `list_university_csvs(data_dir)` - Scans directory, returns sorted list of CSV files
- `get_csv_path(data_dir, csv_name)` - Constructs full path to CSV file

---

## 5. HTML Extractors (`faculty-scraper/html_extractors/`)

### `generic.py`

**Purpose:** Generic HTML extraction for Berkeley, UCLA, UIUC, MIT-style pages.

**Function:**
- `extract_generic_text(soup)` - Extracts research text:
  1. Searches for common research headers (h2/h3)
  2. Returns following paragraph if found (>100 chars)
  3. Fallback: Returns largest paragraph (>120 chars)

### `harvard.py`

**Purpose:** Harvard SEAS (Drupal) specific extraction.

**Function:**
- `extract_harvard_text(soup)` - Extracts research text:
  1. Tries CSS selectors in priority order:
     - `.field--name-field-person-research-summary`
     - `.field--name-body`
     - `.node__content`
     - `.field--name-field-person-bio`
  2. Returns first match with >120 chars

---

## Data Flow Summary

```
1. DATA COLLECTION
   ├─ data_cleaner.py (CSV/PDF processing)
   ├─ scraper_bridge/staffspy_ingest.py (LinkedIn scraping)
   └─ faculty-scraper/scripts/*.rb (Faculty directory scraping)

2. DATA ENRICHMENT (Optional)
   └─ faculty-scraper/professor_enrichment/
      ├─ run_enrichment.py (orchestration)
      ├─ scraper.py (web scraping)
      └─ nlp_processor.py (NLP processing)

3. DATA NORMALIZATION (StaffSpy)
   └─ scraper_bridge/normalize_for_outreach.py
      ├─ Hard filtering
      ├─ Role filtering
      ├─ Title normalization
      └─ Email generation

4. DATA INGESTION
   └─ Append to master CSV with campaign state

5. CAMPAIGN EXECUTION
   └─ outreach/campaign.py
      ├─ Filter recipients
      ├─ Select templates
      ├─ Send emails
      └─ Update state
```

---

## Key Design Patterns

1. **Fault Tolerance:**
   - Atomic CSV saves (temporary file + replace)
   - State persistence after each operation
   - Retry logic with exponential backoff
   - Graceful error handling

2. **Separation of Concerns:**
   - Normalization layer separate from scraping
   - Template selection separate from sending
   - Filtering separate from orchestration

3. **Configuration Management:**
   - Environment variables for sensitive data
   - Centralized config files
   - Test mode flags

4. **Data Contracts:**
   - Strict schema enforcement
   - Validation at each stage
   - Rejection tracking with reasons

5. **Modularity:**
   - University-specific extractors
   - Pluggable template system
   - Independent CSV processing

---

## File Dependencies

```
data_cleaner.py
  └─ pandas, pdfplumber

outreach/
  ├─ campaign.py
  │   ├─ config.py
  │   ├─ templates.py
  │   ├─ filters.py
  │   └─ mailer.py
  ├─ config.py (standalone)
  ├─ filters.py
  │   └─ config.py
  ├─ mailer.py
  │   └─ config.py
  └─ templates.py (standalone)

scraper_bridge/
  ├─ staffspy_ingest.py
  │   └─ normalize_for_outreach.py
  └─ normalize_for_outreach.py (standalone)

faculty-scraper/professor_enrichment/
  ├─ run_enrichment.py
  │   ├─ config.py
  │   ├─ scraper.py
  │   └─ utils/data_loader.py
  ├─ scraper.py
  │   ├─ config.py
  │   ├─ nlp_processor.py
  │   └─ html_extractors/generic.py, harvard.py
  ├─ nlp_processor.py
  │   └─ config.py
  └─ config.py (standalone)
```

---

## Testing & Development

**Test Modes:**
- `scripts/data_cleaner.py`: `TEST_MODE` flag limits rows/pages
- `outreach/config.py`: `TEST_MODE` limits to 5 emails
- `faculty-scraper/professor_enrichment/config.py`: `MODE = 'TEST'` limits to 5 rows
- `scraper_bridge/staffspy_ingest.py`: `SAFE_SINGLE_COMPANY_MODE` for single company testing

**Logging:**
- All modules use Python `logging` module
- Log files: `outreach_campaign.log`, `staffspy_ingest_log.txt`
- Log levels: INFO (default), with detail levels for faculty enrichment

---

This overview provides a complete understanding of every code file in the system. Each module is designed to be independent yet integrated into a cohesive pipeline.

