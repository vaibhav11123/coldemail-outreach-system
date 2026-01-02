# Cold Email Outreach Project - Structure Documentation

**Version:** 2.0.0  
**Last Updated:** 2025-01-03  
**Changelog:**
- v2.0.0: Updated for organized directory structure, normalization layer documentation, path updates
- v1.0.0: Initial version

---

## Overview

This project is a comprehensive cold email outreach system designed for automated lead generation, data cleaning, and email campaign management. It consists of four main components:

1. **Data Collection & Cleaning** - Scrapes and processes contact data from multiple sources
2. **Data Enrichment** - Enhances faculty profiles with research information (optional)
3. **Lead Ingestion** - Bridges scraped data into the campaign system
4. **Email Campaign Engine** - Manages automated email sending with follow-up sequences

---

## Root Directory Structure

```
coldemail/
├── outreach/                    # Main email campaign module
├── scraper_bridge/              # LinkedIn scraper and data ingestion
├── faculty-scraper/             # University faculty contact scraper (Ruby-based)
├── data/                        # Data files
│   ├── raw/                     # Raw input data (CSV, PDF)
│   ├── processed/               # Master processed database
│   └── backups/                 # Backup files
├── docs/                        # Documentation files
├── scripts/                     # Root-level scripts
│   └── data_cleaner.py          # CSV/PDF data processing and cleaning
├── logs/                        # Log files
└── config/                      # Configuration files
```

---

## 1. `/outreach/` - Email Campaign Module

The core email campaign engine that manages automated sending, follow-ups, and state tracking.

### Files:

- **`campaign.py`** - Main orchestration script
  - **Critical:** Loads `.env` file BEFORE any imports (ensures credentials available)
  - **Path resolution:** Uses `Path(__file__).parent.parent` to resolve project root, then joins with `config.FILE_TO_LOAD`
  - Loads contact data from `data/processed/cold_email_outreach_all_cleaned_ranked.csv`
  - Initializes tracking columns if missing (`Sent_Status`, timestamps, follow-up columns)
  - **Daily quota management:** Counts emails sent today per campaign stage, enforces limit (450/day default)
  - Filters recipients using `filter_recipients_by_stage()`
  - Applies test mode limit (5 emails) or daily quota limit
  - Establishes SMTP connection once, reuses for all emails
  - **Send loop with atomic saves:**
    - Selects template based on score/title
    - Formats email with personalization
    - Sends via `SMTPMailer.send_email()`
    - Updates status and timestamp immediately
    - **Saves CSV after each success** using `save_campaign_state()` (fault-tolerant atomic save via temp file + `os.replace()`)
    - Random delay (5-15 seconds) between sends
  - Final cleanup and save
  - **Key feature:** State persistence after each email (not batch) for maximum fault tolerance

- **`config.py`** - Configuration and settings
  - SMTP credentials from `.env` file (`SENDER_EMAIL`, `SENDER_PASSWORD`)
  - SMTP server settings (Gmail: `smtp.gmail.com:587`)
  - **File paths:** Uses relative paths from project root:
    - `FILE_TO_LOAD = "data/processed/cold_email_outreach_all_cleaned_ranked.csv"`
    - `LOG_FILE = "logs/outreach_campaign.log"`
  - Campaign stage control (`INITIAL_SEND`, `FOLLOW_UP_1`, `FOLLOW_UP_2`)
  - Daily send limits (default: 450 emails/day)
  - Test mode settings (`TEST_MODE`, `MAX_EMAILS_IN_TEST = 5`)
  - Logging setup via `setup_logging()` function
  - **Validation:** Checks if `SENDER_PASSWORD` is set before proceeding

- **`mailer.py`** - SMTP email sending class
  - **`SMTPMailer` class** manages SMTP connection lifecycle
  - `connect()`: Establishes TLS connection, handles stale connections
  - `disconnect()`: Safely closes connection, handles disconnection errors
  - `send_email()`: Sends single email with retry logic
    - Checks connection before send, reconnects if needed
    - **Retry logic:** 1 retry attempt on `SMTPServerDisconnected`
    - Returns status codes: `SUCCESS`, `FAILED_REFUSED`, `FAILED_OTHER`
  - **Error handling:**
    - `SMTPRecipientsRefused` → `FAILED_REFUSED` (bad email)
    - `SMTPServerDisconnected` → Reconnect and retry
    - Other exceptions → `FAILED_OTHER`
  - 30-second timeout for connections

- **`templates.py`** - Email template management
  - **5 email templates:**
    - `TEMPLATE_1`: Primary cold email (high-score leads, 90-100)
    - `TEMPLATE_2`: Ultra-short version (score < 90)
    - `TEMPLATE_3`: ML-focused version (tech-leaning leaders)
    - `TEMPLATE_4`: First follow-up (6-7 days)
    - `TEMPLATE_5`: Second follow-up (12-14 days, final)
  - **Template selection logic (`get_initial_template`):**
    1. Tech titles (CTO, Head of AI, etc.) → `TEMPLATE_3`
    2. High score (≥90) → `TEMPLATE_1`
    3. Default → `TEMPLATE_2`
  - **Helper functions:**
    - `get_salutation_name()`: Extracts first name, falls back to "Hiring Team"
    - Template variables: `{FirstName}`, `{Company}`

- **`filters.py`** - Recipient filtering logic
  - **`filter_recipients_by_stage(df)`** - Main filtering function
  - **INITIAL_SEND:** Returns all rows where `Sent_Status == 'PENDING'`
  - **FOLLOW_UP_1:**
    - Requires: `Sent_Status == 'SENT_SUCCESS'`
    - Requires: `FollowUp_1_Status` not already sent/failed
    - Time window: 6-8 days after `Sent_Timestamp`
  - **FOLLOW_UP_2:**
    - Requires: Both initial and follow-up 1 successful
    - Requires: `FollowUp_2_Status` not already sent/failed
    - Time window: 6-8 days after `FollowUp_1_Timestamp`
  - **Edge cases:** Initializes missing tracking columns, handles invalid timestamps

### Workflow:
1. `campaign.py` reads configuration from `config.py`
2. Loads master CSV and filters recipients via `filters.py`
3. Selects appropriate template from `templates.py`
4. Sends emails using `mailer.py`
5. Updates CSV with status and timestamps after each send

---

## 2. `/scraper_bridge/` - LinkedIn Scraper & Ingestion

Bridges LinkedIn profile scraping with the campaign system using StaffSpy, with a normalization layer that transforms raw scraping output into outreach-ready data.

### Files:

- **`staffspy_ingest.py`** - Main StaffSpy ingestion pipeline
  - Uses `staffspy` library for LinkedIn profile scraping
  - **Path configuration:** Uses `PROJECT_ROOT` pattern for all file paths:
    - `MASTER_CSV_FOR_DEDUP = data/backups/cold_email_outreach_all_cleaned_ranked.csv.backup`
    - `TARGET_COMPANIES_FILE = config/target_companies.csv`
  - **Normalization layer integration**: Transforms raw scraping output into outreach-ready data
  - **Organized diagnostics**: All output files saved to `diagnostics/company_snapshots/{company}/`
  - **Company-specific folders:** Creates dedicated folder per company for all diagnostic outputs
  - **SAFE mode improvements:** Now loads email format from `target_companies.csv` instead of hardcoding
  - **Production resume logic:** Safely removes processed companies from list using list comprehension
  - Supports SAFE mode (single company testing) and PRODUCTION mode
  - Applies scoring, deduplication, and staging logic
  - **Safe NA handling:** Uses `safe_int()` and `safe_bool()` helpers for pandas NA values
  - Safety guards: randomized delays, error handling, logging

- **`normalize_for_outreach.py`** - **Outreach Normalization Layer (Critical Business Logic)**
  - **Strict schema enforcement:** Outputs only outreach-relevant columns (company, name, role, email, confidence, etc.)
  - **Hard filtering**: Removes invalid profiles (headless, LinkedIn Member, search results, empty headlines)
  - **Role filtering**: Explicit allow/deny lists for decision-adjacent roles
    - **Allowed:** Director, Head, VP, Principal, Staff Engineer, Engineering Manager, Tech Lead, Founder, C-Level
    - **Excluded:** Intern, SDE-1/2, QA, Test, Support, Student, Operations, HR, Recruiter, Junior
  - **Title normalization**: Maps noisy titles to canonical roles with seniority/department mapping
    - Example: "Engineering Manager @ Zepto" → "Engineering Manager" (Manager, Engineering)
    - Includes catch-all for Software Engineer (IC) roles
  - **Email generation with confidence**: Priority-based email generation
    - Priority 1 (0.9): Email format from CSV confirmed
    - Priority 2 (0.6): Extracted from potential_emails
    - Priority 3 (0.3): Fallback pattern (first.last@domain)
  - **Minimum confidence threshold**: Only emails with confidence ≥ 0.3 are accepted
  - **Rejection tracking**: Captures all rejected leads with detailed reasons in `rejected_debug.csv`
  - **Logging**: Uses `logging` module for all output (no print statements)
  - **Returns:** `(outreach_ready_df, rejected_debug_df)` tuple

- **`scraper_to_ingest.py`** - Legacy LinkedIn profile scraper (alternative)
  - Uses Selenium and `linkedin_scraper` library
  - Configurable search queries (via `.env` file)
  - Scrapes profile data: name, title, email, company
  - Applies cleaning and scoring logic
  - Safety guards: max runtime (20 min), max profiles, checkpoint detection
  - Randomized delays to avoid detection
  - Calls `ingest_new_leads()` to save data

- **`enforce_master_schema.py`** - Schema enforcement for verified leads
  - Converts verified leads to campaign-ready master schema
  - **Path configuration:** Uses `PROJECT_ROOT` pattern:
    - `INPUT_CSV = scraper_bridge/final_verified_leads.csv`
    - `OUTPUT_CSV = data/processed/cold_email_outreach_all_cleaned_ranked.csv`
  - Ensures required columns exist (`Name`, `Title`, `Email`, `Company`, `HiringScore`)
  - Adds missing campaign columns with defaults
  - Normalizes types (HiringScore to int, Email to lowercase string)
  - Returns DataFrame with canonical column order

- **`qualify_leads.py`** - Lead qualification and verification
  - **Path configuration:** Uses `PROJECT_ROOT` pattern:
    - `INPUT_CSV = data/processed/cold_email_outreach_all_cleaned_ranked.csv`
    - `OUTPUT_CSV = scraper_bridge/og_final_verified_leads.csv`
  - **DNS verification:** Checks MX records for email domains (cached)
  - **Lead scoring:** Calculates qualification score (0-100) based on:
    - Email syntax validation
    - Role inbox detection (info@, support@, etc.)
    - Domain authority (free vs. corporate)
    - Title authority (founder, VP, director, etc.)
    - Data completeness
    - Name/email consistency
  - Filters out low-quality leads (role inboxes, free domains for corporate contacts)
  - Saves verified leads with qualification scores

### Directory Structure:

```
scraper_bridge/
├── staffspy_ingest.py
├── normalize_for_outreach.py
├── diagnostics/
│   └── company_snapshots/
│       ├── {company_name}/
│       │   ├── staffspy_raw_snapshot.csv      # Raw StaffSpy output
│       │   ├── staffspy_outreach_ready.csv    # Normalized outreach-ready data
│       │   └── staffspy_rejected_debug.csv    # Rejected leads with reasons
│       └── ...
├── staffspy_ingest_log.txt                    # Execution logs
└── staffspy_new_leads_staging.csv            # Staged leads for production
```

### Normalization Process:

1. **Raw Scraping**: StaffSpy scrapes LinkedIn profiles for a company
2. **Hard Filtering**: Removes structurally invalid profiles (headless, hidden, search results)
3. **Role Filtering**: Applies explicit allow/deny lists (removes interns, QA, students, etc.)
4. **Title Normalization**: Maps noisy titles to canonical roles (e.g., "Engineering Manager @ Zepto" → "Engineering Manager")
5. **Email Generation**: Generates emails with confidence scores (0.9 format confirmed, 0.6 inferred, 0.3 fallback)
6. **Schema Enforcement**: Outputs strict outreach schema with only relevant columns
7. **Rejection Tracking**: Saves all rejected leads with detailed reasons

### Workflow:
1. `staffspy_ingest.py` loads target companies from `config/target_companies.csv`
2. For each company, scrapes LinkedIn profiles using StaffSpy
3. Saves raw snapshot to `diagnostics/company_snapshots/{company}/staffspy_raw_snapshot.csv`
4. **Normalizes data** using `normalize_for_outreach()`:
   - Hard filters invalid profiles
   - Filters by role relevance
   - Normalizes titles to canonical roles
   - Generates emails with confidence scores
5. Saves outputs:
   - `staffspy_outreach_ready.csv` - Outreach-ready leads
   - `staffspy_rejected_debug.csv` - Rejected leads with reasons
6. Converts normalized data to legacy format for scoring/staging
7. Applies scoring, deduplication, and staging
8. Saves final leads to staging CSV or test snapshot

### Key Features:

- **Strict Data Contract**: Normalization layer enforces business logic that scrapers don't provide
- **Organized Diagnostics**: All company-specific files in dedicated folders
- **Rejection Tracking**: Understand why leads were dropped
- **Email Confidence**: Minimum 0.3 confidence threshold ensures only actionable emails
- **Role Qualification**: Explicit allow/deny lists prevent non-decision roles from entering pipeline

---

## 3. `/faculty-scraper/` - University Faculty Scraper

Ruby-based scraper for collecting faculty contact information from top universities, with Python-based enrichment capabilities.

### Structure:

- **`scripts/`** - Individual university scrapers
  - One Ruby script per university (e.g., `berkeley.rb`, `mit.rb`, `stanford.rb`)
  - Uses shared bot logic from `scripts/include/bot.rb`
  - Supported universities: Berkeley, MIT, Stanford, Harvard, Oxford, Cambridge, ETH Zurich, and more

- **`data/`** - Scraped faculty data
  - CSV files per university (e.g., `berkeley.csv`, `mit.csv`)
  - Format: `NAME, EMAIL ID, PROFILE LINK`
  - Total: ~4,084 faculty contacts across 16 universities
  - Can be enriched with research data via `professor_enrichment/`

- **`professor_enrichment/`** - Python-based faculty profile enrichment module
  - **`run_enrichment.py`** - Main orchestration script
    - **Multi-CSV Support:** Scans `data/` directory, prompts user to select universities
    - **Harvard URL Generation:** Auto-generates missing Harvard profile URLs from names
      - Uses `generate_harvard_url_from_name()`: Converts "Michael J. Aziz" → `michael-aziz`
      - Fills `PROFILE LINK` column before scraping
    - **Independent Processing:** Each CSV processed separately (no cross-contamination)
    - **Skip/Rerun Logic:** Asks user if they want to re-run already-scraped profiles
    - **Periodic Saves:** Saves CSV every N rows (configurable via `SAVE_EVERY_N_ROWS`)
    - **Sent Status Logic:** Sets `Sent_Status` based on enrichment quality:
      - `PENDING`: `Scrape_Status == 'SUCCESS'` AND `Confidence >= 1`
      - `NEEDS REVIEW`: Otherwise
    - Updates CSV in-place with enriched data
    - **Workflow:**
      1. Scans `data/` for CSV files
      2. User selects universities (or "all")
      3. For each CSV:
         - Loads and validates
         - Detects university type
         - Generates Harvard URLs if needed
         - Initializes enrichment columns
         - Checks for already-scraped profiles
         - Prompts for rerun confirmation
         - Scraping loop with periodic saves
         - Sets `Sent_Status` based on results
         - Final save and summary
  
  - **`scraper.py`** - Web scraping functions
    - **`scrape_and_process_profile(row)`** - Main scraping function
    - **URL Validation:** Checks for valid HTTP/HTTPS URLs
    - **URL Normalization:** Converts http → https
    - **Berkeley Fallback URLs:** Generates alternative URLs if main URL fails
    - **Retry Logic:** 3 attempts per URL with exponential backoff (1.5s, 3.0s, 4.5s)
    - **University Detection:** Detects from URL (harvard, ucla, berkeley, uiuc, generic)
    - **University-Aware Extraction:**
      - Harvard → `extract_harvard_text()` (Drupal-specific selectors)
      - UCLA → `extract_ucla_research_text()` (table-based extraction)
      - Generic → `extract_generic_text()` (header-based extraction)
    - **NLP Processing Pipeline:**
      - Extracts primary focus
      - Calculates confidence score (university-aware)
      - Infers research question
      - Builds personalization line
      - Generates subject line
      - Calculates hiring score
      - Infers domain
    - **Error Handling:** Returns structured error response for all failures
    - Returns complete result dictionary with all enrichment fields
  
  - **`nlp_processor.py`** - NLP and scoring functions
    - **Text Processing:**
      - `extract_sentences()`: Splits text into sentences (min 40 chars)
      - `score_sentence()`: Scores sentence based on AI/ML keyword density
      - `extract_primary_focus()`: Extracts best research sentence:
        - Filters out role/biographical sentences
        - Keeps sentences with research verbs
        - Ranks by keyword score
        - Cleans up common prefixes
    - **Scoring:**
      - `confidence_score()`: Calculates 0-3 confidence (university-aware):
        - Signal 1: Length threshold (40 chars, 25 for Harvard)
        - Signal 2: Keyword density (≥2 keywords, ≥1 for Harvard)
        - Signal 3: Research verb presence
      - `calculate_hiring_score()`: Calculates 10-95 score:
        - Base: 10
        - +40: Reinforcement, foundation, robotics, representation, causal
        - +30: Deep learning, optimization, neural, computer vision, generative AI
        - +15: Machine learning, NLP, AI, data science
        - +10: Lab or center mentions
    - **Personalization:**
      - `build_personalization_line()`: Confidence-aware personalization (0-3 scale)
      - `generate_subject_line()`: Confidence-aware subject lines
      - `infer_research_question()`: Converts research statement to implicit question
    - **Domain Inference:**
      - `infer_domain()`: Categorizes research (Robotics/RL, Vision, NLP, Foundations, Data Science, General ML)
    - **Helper Functions:**
      - `is_role_sentence()`: Detects biographical/role sentences
      - `has_research_signal()`: Detects research activity verbs
  
  - **`config.py`** - Configuration settings
    - **Mode Control:** `MODE = 'TEST'` or `'PROD'`
    - **Logging:** `LOG_DETAIL` (0=minimal, 1=medium, 2=full)
    - **Testing:** `TEST_ROW_LIMIT = 5` (rows processed in test mode)
    - **Periodic Saves:** `SAVE_EVERY_N_ROWS = 5`
    - **Data Directory:** Auto-detected path to `data/` folder
    - **Rate Limiting:** `BASE_SLEEP_TIME = 1.5s`, `REQUESTS_TIMEOUT = 10s`
    - **AI/ML Keywords:** List of keywords for scoring (machine learning, deep learning, etc.)
    - **NLP Filtering:** `BAD_SENTENCE_PATTERNS`, `RESEARCH_VERBS`
    - **Personalization Tone:** Presets for high/medium/low confidence
    - **HTTP Headers:** User-Agent and Accept-Language for scraping
  
  - **`utils/data_loader.py`** - Data loading utilities
    - `list_university_csvs(data_dir)`: Scans directory, returns sorted list of CSV files
    - `get_csv_path(data_dir, csv_name)`: Constructs full path to CSV file

- **`html_extractors/`** - University-specific HTML extraction modules
  - **`generic.py`** - Generic extraction for Berkeley, UCLA, UIUC, MIT-style pages
    - `extract_generic_text(soup)`: 
      - Searches for common research headers (h2/h3: "Research", "Research Interests", "Research Areas")
      - Returns following paragraph if found (>100 chars)
      - Fallback: Returns largest paragraph (>120 chars)
  - **`harvard.py`** - Harvard SEAS (Drupal) specific extraction
    - `extract_harvard_text(soup)`:
      - Tries CSS selectors in priority order:
        1. `.field--name-field-person-research-summary`
        2. `.field--name-body`
        3. `.node__content`
        4. `.field--name-field-person-bio`
      - Returns first match with >120 chars
  - **Modular design:** Easy to add new university extractors by creating new functions

  **Enrichment Output Columns:**
  - `Primary_Focus` - Best research sentence extracted
  - `Source_Sentence` - Original sentence used
  - `Research_Question_Hint` - Generated research question
  - `Personalization_Line` - Generated email personalization hook
  - `Email_Subject` - Generated email subject line
  - `HiringScore` - Calculated score (10-95) based on research focus
  - `Confidence` - Extraction reliability (0, 1, or 2)
  - `Research_Areas` - Full research content scraped
  - `Domain` - Research domain category
  - `Scrape_Status` - Success/failure status
  - `Error_Detail` - Error information if scraping failed

- **`README.md`** - Documentation for the faculty scraper tool

### Workflow:
1. Run Ruby scrapers to collect basic faculty data (name, email, profile link)
2. Run `python -m faculty-scraper.professor_enrichment.run_enrichment`
   - Select which universities to process (interactive prompt)
   - Choose whether to re-run already-scraped profiles
   - Each CSV is processed independently and saved in-place
3. Enriched data can be processed through `data_cleaner.py` to integrate with campaign system

### Note:
The enrichment module adds research-focused personalization capabilities, making it ideal for academic outreach campaigns targeting professors and researchers.

---

## 4. Root-Level Files

### Data Processing:

- **`scripts/data_cleaner.py`** - Master data cleaning script
  - **Path configuration:** Uses relative paths from `scripts/` directory:
    - `CSV_FILE = "../data/raw/14400+ Ultimate HR Outreach List...csv"`
    - `PDF_FILE = "../data/raw/Company Wise HR Contacts - HR Contacts.pdf"`
    - `OUTPUT_FILE = "../data/processed/cold_email_outreach_all_cleaned_ranked.csv"`
  - **CSV Processing (`process_csv`):**
    - Reads CSV file (skips first 3 rows)
    - Renames columns, normalizes data
    - Validates emails (regex pattern, excludes URLs/forms)
    - Applies cleaning functions to all text fields
  - **PDF Processing (`parse_hr_pdf`):**
    - Uses `pdfplumber` to extract tables
    - Heuristic mapping: First cell → Name, Last cell → Company, Middle → Title/Email
    - Extracts email from text blob using regex
    - Only processes rows with valid emails
  - **Cleaning Functions:**
    - `clean_email()`: Removes invalid characters, normalizes to lowercase
    - `clean_text()`, `clean_name()`, `clean_title()`, `clean_company()`: Text normalization
  - **Hiring Score Calculation (`hiring_score`):**
    - Founders/CEOs: 100
    - CHRO: 90
    - VPs: 80
    - Directors: 70
    - HR Heads: 60
    - Talent Acquisition: 50
    - General HR: 30
    - Default: 10
  - **Main Function:**
    - Processes both CSV and PDF
    - Concatenates DataFrames
    - Validates emails with regex pattern
    - Calculates `HiringScore` for each row
    - Sorts by `HiringScore` (descending)
    - Removes duplicates (by Email + Company)
    - Outputs: `data/processed/cold_email_outreach_all_cleaned_ranked.csv`
  - **Test Mode:** Can limit CSV rows and PDF pages for testing

### Data Files:

- **`cold_email_outreach_all_cleaned_ranked.csv`** - Master contact database
  - Columns:
    - Contact info: `Name`, `Title`, `Email`, `Company`, `Location`
    - Metadata: `Source`, `HiringScore`
    - Campaign state: `Sent_Status`, `Sent_Timestamp`, `FollowUp_1_Status`, `FollowUp_1_Timestamp`, `FollowUp_2_Status`, `FollowUp_2_Timestamp`
    - Enrichment data (if from faculty scraper): `Primary_Focus`, `Personalization_Line`, `Research_Areas`, `Domain`, `Confidence`
  - Sorted by `HiringScore` (descending)
  - This is the single source of truth for all campaigns

- **`data/backups/cold_email_outreach_all_cleaned_ranked.csv.backup`** - Backup of master CSV

- **`data/raw/14400+ Ultimate HR Outreach List  - DataNiti - 2500+ HR's Manager Contacts with Profiles - .csv`** - Raw input data

- **`data/raw/Company Wise HR Contacts - HR Contacts.pdf`** - Raw PDF input data

### Logs:

- **`logs/outreach_campaign.log`** - Campaign execution logs
  - Records all email sends, failures, and system events
  - Timestamped entries for debugging and auditing

### Documentation:

- **`TESTING_GUIDE.md`** - Comprehensive testing documentation
  - Unit testing guidelines
  - Integration testing procedures
  - System testing workflows
  - Performance and deliverability checks

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA COLLECTION                           │
├─────────────────────────────────────────────────────────────┤
│ 1. Raw CSV/PDF files                                         │
│ 2. LinkedIn scraper (scraper_bridge/staffspy_ingest.py)      │
│ 3. Faculty scraper (faculty-scraper/scripts/)                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATA ENRICHMENT (Optional)                 │
├─────────────────────────────────────────────────────────────┤
│ faculty-scraper/professor_enrichment/                        │
│  ├─ Scrapes faculty profile pages                           │
│  ├─ Extracts research areas (NLP processing)                │
│  ├─ Calculates research-based HiringScore                   │
│  ├─ Generates personalization lines                         │
│  └─ Updates faculty CSV files in-place                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              DATA NORMALIZATION (StaffSpy)                    │
├─────────────────────────────────────────────────────────────┤
│ scraper_bridge/normalize_for_outreach.py                      │
│  ├─ Hard filters invalid profiles                           │
│  ├─ Role filtering (allow/deny lists)                      │
│  ├─ Title normalization (canonical roles)                   │
│  ├─ Email generation (with confidence scores)              │
│  └─ Schema enforcement (strict outreach schema)             │
│                                                              │
│ Outputs:                                                     │
│  ├─ staffspy_outreach_ready.csv (normalized leads)          │
│  └─ staffspy_rejected_debug.csv (rejected with reasons)     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATA PROCESSING                           │
├─────────────────────────────────────────────────────────────┤
│ data_cleaner.py                                              │
│  ├─ Cleans and normalizes data                              │
│  ├─ Calculates HiringScore                                  │
│  └─ Removes duplicates                                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATA INGESTION                            │
├─────────────────────────────────────────────────────────────┤
│ scraper_bridge/ingest_function.py                           │
│  ├─ Appends new leads to master CSV                         │
│  ├─ Prevents duplicates                                     │
│  └─ Initializes campaign state                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              MASTER DATABASE (CSV)                            │
├─────────────────────────────────────────────────────────────┤
│ cold_email_outreach_all_cleaned_ranked.csv                  │
│  └─ Single source of truth for all contacts                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  CAMPAIGN EXECUTION                          │
├─────────────────────────────────────────────────────────────┤
│ outreach/campaign.py                                         │
│  ├─ Filters recipients (filters.py)                         │
│  ├─ Selects templates (templates.py)                          │
│  ├─ Sends emails (mailer.py)                                │
│  └─ Updates CSV state                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Campaign Stages

The system supports three campaign stages, controlled by `config.CAMPAIGN_STAGE`:

1. **`INITIAL_SEND`** - First contact email
   - Targets: All contacts with `Sent_Status = 'PENDING'`
   - Template selection based on HiringScore and job title

2. **`FOLLOW_UP_1`** - First follow-up (6-8 days after initial send)
   - Targets: Contacts with `Sent_Status = 'SENT_SUCCESS'` and timestamp 6-8 days old
   - Uses `TEMPLATE_4` (short follow-up)

3. **`FOLLOW_UP_2`** - Final follow-up (6-8 days after follow-up 1)
   - Targets: Contacts with both initial and follow-up 1 successful
   - Uses `TEMPLATE_5` (closing message)

---

## Configuration

The system uses environment variables (`.env` file) for sensitive configuration:

### Required Variables:
- `SENDER_EMAIL` - Gmail address for sending
- `SENDER_PASSWORD` - Gmail app password
- `LINKEDIN_EMAIL` - LinkedIn login email
- `LINKEDIN_PASSWORD` - LinkedIn login password
- `QUERY_1`, `QUERY_2`, ... - LinkedIn search queries

### Optional Variables:
- `MAX_PROFILES_TO_SCRAPE` - Max profiles to scrape (default: 30)
- `SCRAPER_MODE` - `TEST` or `PROD` (default: `TEST`)
- Various delay settings for scraper

---

## Key Features

1. **Fault Tolerance**
   - Atomic CSV saves prevent data loss
   - SMTP reconnection logic
   - State persistence after each email

2. **Safety Mechanisms**
   - Daily send limits (450 emails/day default)
   - Randomized delays between sends (5-15 seconds)
   - Test mode for dry runs
   - Runtime limits for scraper (20 minutes)

3. **Smart Template Selection**
   - High-score leads get detailed templates
   - Tech titles get ML-focused templates
   - Low-score leads get short templates

4. **Duplicate Prevention**
   - Email-based duplicate checking during ingestion

4. **Comprehensive Logging**
   - All operations logged to `logs/outreach_campaign.log`
   - Timestamped entries for auditing

---

## Usage Workflow

1. **Initial Setup:**
   ```bash
   # Process raw data
   python scripts/data_cleaner.py
   
   # Or scrape new leads (StaffSpy - recommended)
   cd scraper_bridge
   python staffspy_ingest.py
   
   # Or use legacy scraper
   python scraper_to_ingest.py
   
   # Or enrich faculty data (optional)
   python -m faculty-scraper.professor_enrichment.run_enrichment
   ```

2. **Run Campaign:**
   ```bash
   # Edit outreach/config.py to set CAMPAIGN_STAGE
   python -m outreach.campaign
   ```

3. **Monitor:**
   - Check `logs/outreach_campaign.log` for execution details
   - Review CSV file for updated statuses
   - Verify sent emails in your email account

---

## Dependencies

### Python Packages:
- `pandas` - Data manipulation
- `smtplib` - Email sending (built-in)
- `selenium` - Web scraping
- `linkedin_scraper` - LinkedIn profile scraping (legacy)
- `staffspy` - LinkedIn profile scraping (StaffSpy library, recommended)
- `pdfplumber` - PDF parsing
- `python-dotenv` - Environment variable management
- `requests` - HTTP requests (for professor enrichment)
- `beautifulsoup4` - HTML parsing (for professor enrichment)

### Ruby (for faculty-scraper):
- Ruby runtime
- Various gems (see `faculty-scraper/` for details)

---

## Notes

- The master CSV file (`data/processed/cold_email_outreach_all_cleaned_ranked.csv`) is the single source of truth
- Always backup the CSV before running campaigns
- Test mode should be used for initial testing (sends only 5 emails)
- The system is designed to be run daily, respecting quota limits
- Follow-up emails are automatically scheduled based on timestamps

