# Cold Email Outreach Project - Structure Documentation

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
├── data_cleaner.py              # CSV/PDF data processing and cleaning
├── cold_email_outreach_all_cleaned_ranked.csv  # Master contact database
├── outreach_campaign.log        # Campaign execution logs
└── TESTING_GUIDE.md            # Testing documentation
```

---

## 1. `/outreach/` - Email Campaign Module

The core email campaign engine that manages automated sending, follow-ups, and state tracking.

### Files:

- **`campaign.py`** - Main orchestration script
  - Loads contact data from CSV
  - Filters recipients based on campaign stage
  - Manages email sending loop with state persistence
  - Implements daily quota limits and safety delays
  - Handles atomic CSV saves for fault tolerance

- **`config.py`** - Configuration and settings
  - SMTP credentials (loaded from `.env` file)
  - Campaign stage control (`INITIAL_SEND`, `FOLLOW_UP_1`, `FOLLOW_UP_2`)
  - Daily send limits (default: 450 emails/day)
  - Test mode settings
  - Logging setup

- **`mailer.py`** - SMTP email sending class
  - `SMTPMailer` class manages SMTP connection lifecycle
  - Handles connection retries and error recovery
  - Returns status codes: `SUCCESS`, `FAILED_REFUSED`, `FAILED_OTHER`
  - Implements timeout and disconnection handling

- **`templates.py`** - Email template management
  - 5 email templates (3 initial, 2 follow-ups)
  - Template selection logic based on:
    - Hiring score (high-score leads get detailed template)
    - Job title (tech titles get ML-focused template)
  - Name extraction and personalization helpers

- **`filters.py`** - Recipient filtering logic
  - Filters contacts by campaign stage
  - Time-based filtering for follow-ups (6-8 day windows)
  - Ensures proper sequencing: Initial → Follow-up 1 → Follow-up 2

### Workflow:
1. `campaign.py` reads configuration from `config.py`
2. Loads master CSV and filters recipients via `filters.py`
3. Selects appropriate template from `templates.py`
4. Sends emails using `mailer.py`
5. Updates CSV with status and timestamps after each send

---

## 2. `/scraper_bridge/` - LinkedIn Scraper & Ingestion

Bridges LinkedIn profile scraping with the campaign system.

### Files:

- **`scraper_to_ingest.py`** - LinkedIn profile scraper
  - Uses Selenium and `linkedin_scraper` library
  - Configurable search queries (via `.env` file)
  - Scrapes profile data: name, title, email, company
  - Applies cleaning and scoring logic
  - Safety guards: max runtime (20 min), max profiles, checkpoint detection
  - Randomized delays to avoid detection
  - Calls `ingest_new_leads()` to save data

- **`ingest_function.py`** - Data ingestion bridge
  - Appends new leads to master CSV (`cold_email_outreach_all_cleaned_ranked.csv`)
  - Prevents duplicates by checking existing emails
  - Initializes campaign state columns:
    - `Sent_Status`, `Sent_Timestamp`
    - `FollowUp_1_Status`, `FollowUp_1_Timestamp`
    - `FollowUp_2_Status`, `FollowUp_2_Timestamp`
  - Sets all new leads to `PENDING` status

### Workflow:
1. `scraper_to_ingest.py` logs into LinkedIn
2. Executes configured search queries
3. Scrapes profile details with delays
4. Cleans and scores each lead
5. Calls `ingest_function.py` to append to master CSV
6. New leads are ready for campaign engine

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
    - Scans `data/` directory for all CSV files
    - Interactive university selection (supports "all" or comma-separated numbers)
    - Processes multiple CSVs independently (no data corruption)
    - Asks for re-run confirmation on already-scraped profiles
    - Periodic saves during processing
    - Updates CSV in-place with enriched data
    - Sets `Sent_Status` based on enrichment quality
  
  - **`scraper.py`** - Web scraping functions
    - `scrape_and_process_profile()` - Main scraping function
    - University-aware extraction (Harvard, UCLA, generic)
    - Retry logic with exponential backoff
    - Handles HTTP errors and network failures gracefully
    - Returns structured data with error handling
  
  - **`nlp_processor.py`** - NLP and scoring functions
    - `extract_primary_focus()` - Extracts best research sentence using keyword scoring
    - `calculate_hiring_score()` - Scores professors based on research topics (AI/ML focus)
    - `build_personalization_line()` - Generates personalized email hooks
    - `infer_domain()` - Categorizes research into domains (Robotics, NLP, Vision, etc.)
    - `confidence_score()` - Calculates extraction reliability (0-2 scale)
    - `infer_research_question()` - Generates research question hints
    - `generate_subject_line()` - Creates email subject lines
  
  - **`config.py`** - Configuration settings
    - Mode control (`TEST` vs `PROD`)
    - Data directory path (no hard-coded CSV files)
    - Rate limiting and timeout settings
    - AI/ML keywords for scoring
    - NLP filtering patterns and research verbs
    - Personalization tone presets
    - HTTP headers for scraping
  
  - **`utils/data_loader.py`** - Data loading utilities
    - `list_university_csvs()` - Scans data directory for CSV files
    - `get_csv_path()` - Builds full paths to CSV files

- **`html_extractors/`** - University-specific HTML extraction modules
  - **`generic.py`** - Generic extraction for Berkeley, UCLA, UIUC, MIT-style pages
  - **`harvard.py`** - Harvard SEAS (Drupal) specific extraction
  - Modular design allows easy addition of new university extractors

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

- **`data_cleaner.py`** - Master data cleaning script
  - Processes CSV files (HR contact lists)
  - Extracts data from PDF files (company-wise HR contacts)
  - Cleans and normalizes: emails, names, titles, companies
  - Calculates `HiringScore` based on job titles:
    - Founders/CEOs: 100
    - CHRO: 90
    - VPs: 80
    - Directors: 70
    - HR Heads: 60
    - Talent Acquisition: 50
    - General HR: 30
  - Removes duplicates and invalid emails
  - Outputs: `cold_email_outreach_all_cleaned_ranked.csv`

### Data Files:

- **`cold_email_outreach_all_cleaned_ranked.csv`** - Master contact database
  - Columns:
    - Contact info: `Name`, `Title`, `Email`, `Company`, `Location`
    - Metadata: `Source`, `HiringScore`
    - Campaign state: `Sent_Status`, `Sent_Timestamp`, `FollowUp_1_Status`, `FollowUp_1_Timestamp`, `FollowUp_2_Status`, `FollowUp_2_Timestamp`
    - Enrichment data (if from faculty scraper): `Primary_Focus`, `Personalization_Line`, `Research_Areas`, `Domain`, `Confidence`
  - Sorted by `HiringScore` (descending)
  - This is the single source of truth for all campaigns

- **`cold_email_outreach_all_cleaned_ranked.csv.backup`** - Backup of master CSV

- **`14400+ Ultimate HR Outreach List  - DataNiti - 2500+ HR's Manager Contacts with Profiles - .csv`** - Raw input data

- **`Company Wise HR Contacts - HR Contacts.pdf`** - Raw PDF input data

### Logs:

- **`outreach_campaign.log`** - Campaign execution logs
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
│ 2. LinkedIn scraper (scraper_bridge/)                        │
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
│  ├─ Selects templates (templates.py)                        │
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
   - All operations logged to `outreach_campaign.log`
   - Timestamped entries for auditing

---

## Usage Workflow

1. **Initial Setup:**
   ```bash
   # Process raw data
   python data_cleaner.py
   
   # Or scrape new leads
   cd scraper_bridge
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
   - Check `outreach_campaign.log` for execution details
   - Review CSV file for updated statuses
   - Verify sent emails in your email account

---

## Dependencies

### Python Packages:
- `pandas` - Data manipulation
- `smtplib` - Email sending (built-in)
- `selenium` - Web scraping
- `linkedin_scraper` - LinkedIn profile scraping
- `pdfplumber` - PDF parsing
- `python-dotenv` - Environment variable management
- `requests` - HTTP requests (for professor enrichment)
- `beautifulsoup4` - HTML parsing (for professor enrichment)

### Ruby (for faculty-scraper):
- Ruby runtime
- Various gems (see `faculty-scraper/` for details)

---

## Notes

- The master CSV file (`cold_email_outreach_all_cleaned_ranked.csv`) is the single source of truth
- Always backup the CSV before running campaigns
- Test mode should be used for initial testing (sends only 5 emails)
- The system is designed to be run daily, respecting quota limits
- Follow-up emails are automatically scheduled based on timestamps

