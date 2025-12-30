# Cold Email Outreach System

**A full-stack, autonomous system targeting 4,000+ top university professors and 14,000+ corporate leaders.** This comprehensive, production-grade cold email outreach engine automates lead generation, data enrichment, and multi-stage campaign management, featuring intelligent, NLP-driven personalization for high-conversion academic and professional outreach.

---

## 📊 Project Scale & Results

This system was engineered to handle large, heterogeneous datasets and execute high-precision campaigns.

| Audience / Metric | Result | Feature Highlight |
| :--- | :--- | :--- |
| **Total Leads Processed** | **~18,500+** Contacts | End-to-end Data Pipeline |
| **Academic Leads** | **4,084 Professors** from **16 Top Global Universities** | **NLP-Based Research Enrichment** |
| **Corporate Leads** | **14,400+ Executives** (CEOs, VPs, CHROs) | **Title-Based HiringScore** & Cleansing |
| **Fault Tolerance** | **100% Data Recovery** | Atomic CSV Saves & SMTP Retry Logic |

---

## 🚀 Features

- **Multi-Source Data Collection**: LinkedIn scraping, faculty directory scraping, CSV/PDF processing
- **Intelligent Data Enrichment**: NLP-based research extraction and personalization for academic contacts
- **Automated Email Campaigns**: Multi-stage campaigns with follow-up sequences
- **Fault-Tolerant Design**: Atomic saves, retry logic, state persistence
- **University-Aware Scraping**: Specialized extractors for different university websites
- **Scalable Architecture**: Process multiple universities independently without data corruption

## 📁 Project Structure

```
coldemail/
├── outreach/                    # Email campaign engine
│   ├── campaign.py             # Main orchestration (atomic saves, quota management)
│   ├── config.py                # Configuration (SMTP, campaign stages)
│   ├── filters.py               # Recipient filtering by stage
│   ├── mailer.py                # SMTP connection and email sending
│   └── templates.py             # Email templates and selection logic
├── scraper_bridge/              # LinkedIn scraper and ingestion
│   ├── staffspy_ingest.py       # Main StaffSpy pipeline
│   ├── normalize_for_outreach.py # Normalization layer (hard filter, role filter, email gen)
│   └── diagnostics/             # Organized output files
├── faculty-scraper/             # University faculty scraper
│   ├── professor_enrichment/    # Research enrichment module
│   │   ├── run_enrichment.py   # Multi-CSV orchestration
│   │   ├── scraper.py          # Web scraping with retry logic
│   │   ├── nlp_processor.py     # NLP processing and scoring
│   │   ├── config.py           # Configuration
│   │   └── utils/data_loader.py # Data loading utilities
│   ├── html_extractors/        # University-specific extractors
│   │   ├── generic.py          # Generic extraction
│   │   └── harvard.py          # Harvard SEAS extraction
│   └── data/                    # Faculty CSV files
├── data_cleaner.py              # CSV/PDF processing and cleaning
└── cold_email_outreach_all_cleaned_ranked.csv  # Master database
```

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for detailed documentation.
See [CODEBASE_OVERVIEW.md](CODEBASE_OVERVIEW.md) for complete code file understanding.

## 🛠️ Installation

### Prerequisites

- Python 3.8+
- Ruby (for faculty scraper scripts)
- Gmail account with App Password enabled
- LinkedIn account (for LinkedIn scraper)

### Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd coldemail
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   
   Create a `.env` file in the project root (see [ENV_SETUP_GUIDE.md](ENV_SETUP_GUIDE.md) for details):
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

## 📖 Quick Start

### 1. Process Raw Data

```bash
# Clean and process CSV/PDF files
python data_cleaner.py
```

### 2. Enrich Faculty Data (Optional)

```bash
# Interactive university selection
python -m faculty-scraper.professor_enrichment.run_enrichment
```

### 3. Scrape LinkedIn Leads (Optional)

```bash
cd scraper_bridge
# Using StaffSpy (recommended - includes normalization layer)
python staffspy_ingest.py

# Or using legacy scraper
python scraper_to_ingest.py
```

**Note:** The StaffSpy ingestion pipeline (`staffspy_ingest.py`) includes a normalization layer that:
- Hard filters invalid profiles
- Applies role-based filtering (removes interns, QA, students, etc.)
- Normalizes titles to canonical roles
- Generates emails with confidence scores
- Saves organized diagnostics to `scraper_bridge/diagnostics/company_snapshots/{company}/`

### 4. Run Email Campaign

```bash
# Edit outreach/config.py to set CAMPAIGN_STAGE
python -m outreach.campaign
```

## ⚙️ Configuration

### Campaign Configuration

Edit `outreach/config.py`:
- `CAMPAIGN_STAGE`: `'INITIAL_SEND'`, `'FOLLOW_UP_1'`, or `'FOLLOW_UP_2'`
- `DAILY_SEND_LIMIT`: Maximum emails per day (default: 450)
- `TEST_MODE`: Set to `True` for testing (sends only 5 emails)

### Enrichment Configuration

Edit `faculty-scraper/professor_enrichment/config.py`:
- `MODE`: `'TEST'` or `'PROD'`
- `TEST_ROW_LIMIT`: Number of rows to process in test mode (default: 5)
- `SAVE_EVERY_N_ROWS`: Periodic save frequency (default: 5)

## 📊 Data Flow

```
Data Collection → Data Enrichment → Data Processing → Lead Ingestion → Campaign Execution
```

1. **Collection**: Scrape from LinkedIn, faculty directories, or load from CSV/PDF
2. **Enrichment**: Extract research areas, generate personalization lines
3. **Processing**: Clean, normalize, score, and deduplicate
4. **Ingestion**: Add to master CSV with campaign state initialization
5. **Execution**: Filter, template selection, send emails, update state

## 🔒 Security

- **Never commit `.env` file** - Contains sensitive credentials
- Use Gmail App Passwords (not regular passwords)
- Review `.gitignore` to ensure sensitive files are excluded
- Rotate credentials periodically

## 📝 Environment Variables

See [ENV_SETUP_GUIDE.md](ENV_SETUP_GUIDE.md) for complete setup instructions.

Required variables:
- `SENDER_EMAIL` - Gmail address
- `SENDER_PASSWORD` - Gmail App Password
- `LINKEDIN_EMAIL` - LinkedIn login
- `LINKEDIN_PASSWORD` - LinkedIn password
- `QUERY_1`, `QUERY_2`, ... - LinkedIn search queries

## 🧪 Testing

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for comprehensive testing procedures.

Quick test:
```bash
# Set TEST_MODE = True in outreach/config.py
python -m outreach.campaign
```

## 📚 Documentation

- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Detailed project structure
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Testing procedures
- [ENV_SETUP_GUIDE.md](ENV_SETUP_GUIDE.md) - Environment configuration

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## ⚠️ Important Notes

- Always backup your CSV files before running campaigns
- Test mode should be used for initial testing
- Respect daily email limits to avoid account suspension
- Follow-up emails are automatically scheduled based on timestamps
- Each university CSV is processed independently (no cross-contamination)

## 📄 License

[Add your license here]

## 🙏 Acknowledgments

- Faculty scraper based on [barc-iitkgp/faculty-scraper](https://github.com/barc-iitkgp/faculty-scraper)

