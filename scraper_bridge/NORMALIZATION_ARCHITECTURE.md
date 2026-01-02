# Outreach Normalization Architecture

**Version:** 1.0.0  
**Last Updated:** 2025-01-03  
**Changelog:**
- v1.0.0: Initial version documenting normalization layer architecture

---

## The Problem (What Was Wrong)

The original pipeline treated **raw scraping output as outreach-ready data**. This violated a fundamental principle:

> **Scraping ≠ Outreach**

### Issues Identified:

1. **No Data Contract**: Raw StaffSpy output has 60+ columns mixing identity, metadata, profile text, and scraper artifacts
2. **No Hard Filtering**: "Headless" profiles, search result links, and "LinkedIn Member" entries were not filtered out
3. **No Role Qualification**: Interns, QA, students, and other non-decision roles were included
4. **No Title Normalization**: Noisy titles like "Engineering Manager @ Zepto" weren't mapped to canonical roles
5. **Email Logic Flawed**: `potential_emails` was used directly without confidence scoring or format validation
6. **No Rejection Tracking**: No way to understand why leads were dropped

---

## The Solution: Normalization Layer

### Architecture Overview

```
Raw StaffSpy Output
    ↓
[normalize_for_outreach.py]
    ↓
    ├─→ Hard Filter (invalid profiles)
    ├─→ Role Filter (allow/deny lists)
    ├─→ Title Normalization (canonical roles)
    ├─→ Email Generation (with confidence)
    └─→ Schema Enforcement
    ↓
Outreach-Ready CSV (strict schema)
    ↓
[staffspy_ingest.py]
    ↓
Scoring → Deduplication → Staging
```

---

## Step-by-Step Normalization Process

### STEP 1: Hard Filter Invalid Profiles

**What it removes:**
- `name == "LinkedIn Member"` (hidden profiles)
- `profile_link` contains `/search/results/` (not real profiles)
- `profile_id == "headless"` (failed profile resolution)
- `headline` is empty (no role information)

**Why:** These are structurally unrecoverable. No NLP, no retry, no magic.

**Output:** Valid profiles only

---

### STEP 2: Role Relevance Filtering

**Allowed Keywords (Decision-adjacent roles):**
- Leadership: `director`, `head`, `vp`, `principal`, `staff engineer`, `engineering manager`, `tech lead`
- Senior IC: `senior engineer`, `staff`, `principal engineer`
- Product: `product manager`, `head of product`, `vp product`

**Excluded Keywords (Non-decision roles):**
- `intern`, `sde-1`, `sde-2`, `qa`, `test`, `support`, `student`
- `operations`, `facilities`, `supply chain`, `hr`, `talent`, `recruiter`
- `delivery`, `logistics`, `facility`, `admin`, `junior`, `entry level`

**Why:** Cold email works when titles are decision-adjacent and personas are stable. Including interns/QA kills conversion.

**Output:** Only relevant roles

---

### STEP 3: Title Normalization

**Maps noisy titles to canonical roles:**

| Raw Headline | Canonical Role | Seniority | Department |
|-------------|---------------|-----------|------------|
| Engineering Manager @ Zepto | Engineering Manager | Manager | Engineering |
| Director of Engineering | Director of Engineering | Director | Engineering |
| VP Engineering - Infra | VP Engineering | VP | Engineering |
| Tech Lead | Tech Lead | Lead | Engineering |
| Software Engineer | Software Engineer (IC) | IC | Engineering |
| Developer | Software Engineer (IC) | IC | Engineering |

**Key Features:**
- **Catch-all IC roles**: Generic engineering titles (software engineer, developer, SDE) that pass the role filter are normalized to "Software Engineer (IC)"
- **Pattern matching**: Uses regex patterns to match noisy titles to canonical roles
- **Automatic seniority/department mapping**: Each canonical role maps to seniority level and department

**Why:** Enables personalization, batch messaging, and performance tracking by persona.

**Output:** Normalized roles with seniority and department

---

### STEP 4: Email Generation with Confidence

**Priority order:**

1. **Email Format from CSV** (confidence: 0.9)
   - Uses `Estimated Email Format` from `target_companies.csv`
   - Pattern: `first.last@company.com`
   - **Requires valid domain extraction** - if domain cannot be extracted, falls to next priority

2. **Extract from potential_emails** (confidence: 0.6)
   - Uses first email from StaffSpy's `potential_emails` list
   - These are pattern expansions, not verified

3. **Fallback Pattern** (confidence: 0.3)
   - Uses extracted domain from email format: `first.last@{domain}`
   - **Minimum confidence threshold**: Only emails with confidence ≥ 0.3 are accepted
   - If no domain available, lead is rejected

**Rejection Logic:**
- Leads with email confidence < 0.3 are rejected
- Leads without extractable domain are rejected
- Rejection reason: `"Low email confidence ({confidence})"`

**Why:** `potential_emails` are inputs to verification, not final outputs. Using them directly = domain burn. Minimum confidence ensures only actionable emails proceed.

**Output:** Single email per lead with confidence score (0.0-1.0), or rejection if confidence too low

---

### STEP 5: Strict Outreach Schema

**Final CSV columns (non-negotiable):**

```
company
first_name
last_name
role              # Canonical (normalized)
seniority         # IC, Manager, Director, VP, C-Level
department        # Engineering, Product, etc.
linkedin_url
company_domain
email
email_confidence  # 0.0-1.0
source
```

**Why:** If a column doesn't directly improve open rate or reply rate, it doesn't belong.

---

## Output Files

### 1. `staffspy_outreach_ready.csv`

**Location:** `scraper_bridge/diagnostics/company_snapshots/{company}/staffspy_outreach_ready.csv`

**Purpose:** What you actually email

**Schema:** Strict outreach schema (see above)

**Guarantees:**
- All rows have valid emails (confidence ≥ 0.3)
- All rows have normalized roles
- All rows passed hard filtering
- All rows are decision-adjacent roles

---

### 2. `staffspy_rejected_debug.csv`

**Location:** `scraper_bridge/diagnostics/company_snapshots/{company}/staffspy_rejected_debug.csv`

**Purpose:** Understand why leads were dropped

**Contains:**
- Original raw row data
- `rejection_reason` column explaining why it was rejected

**Rejection reasons:**
- `"LinkedIn Member (hidden profile)"`
- `"Headless profile_id"`
- `"Search results URL (not real profile)"`
- `"Empty headline"`
- `"Structural hard filter"` (general hard filter rejection)
- `"Excluded role keyword"`
- `"Role not in allowlist or denylist"`
- `"Could not normalize role"` (title doesn't match any normalization pattern)
- `"Low email confidence ({confidence})"` (email confidence < 0.3)

**Why:** This is how you improve scraper quality without guessing.

---

### 3. `staffspy_raw_snapshot.csv`

**Location:** `scraper_bridge/diagnostics/company_snapshots/{company}/staffspy_raw_snapshot.csv`

**Purpose:** Raw StaffSpy output for inspection

**Why:** Always save raw data. You can't recreate it.

**Note:** All diagnostic files are now organized in company-specific folders under `scraper_bridge/diagnostics/company_snapshots/` for better organization and easier debugging.

---

## Integration with Existing Pipeline

The normalization layer sits **between scraping and scoring**:

```python
# In staffspy_ingest.py

# 1. Scrape raw data
df = account.scrape_staff(...)

# 2. Create company-specific diagnostics directory
COMPANY_DIAGNOSTICS_DIR = os.path.join(
    DIAGNOSTICS_BASE_DIR, company_lower
)
os.makedirs(COMPANY_DIAGNOSTICS_DIR, exist_ok=True)

# 3. Save raw snapshot
raw_snapshot_path = os.path.join(
    COMPANY_DIAGNOSTICS_DIR, "staffspy_raw_snapshot.csv"
)
df.to_csv(raw_snapshot_path, index=False)

# 4. NORMALIZE (new layer)
outreach_df, rejected_df = normalize_for_outreach(
    raw_df=df,
    company_name=company,
    email_format=email_format
)

# 5. Save outputs to organized directories
outreach_path = os.path.join(
    COMPANY_DIAGNOSTICS_DIR, "staffspy_outreach_ready.csv"
)
outreach_df.to_csv(outreach_path, index=False)

rejected_path = os.path.join(
    COMPANY_DIAGNOSTICS_DIR, "staffspy_rejected_debug.csv"
)
rejected_df.to_csv(rejected_path, index=False)

# 6. Continue with existing scoring/staging
# (converts normalized schema to legacy format for compatibility)
```

---

## Key Principles

1. **Scraping ≠ Outreach**: Scrapers optimize for coverage/speed/volume. Outreach requires precision/filtering/intent alignment.

2. **Normalization is Business Logic**: The normalization layer enforces data contracts that scrapers don't provide.

3. **Hard Filters First**: Remove structurally unrecoverable rows before any processing.

4. **Explicit Allow/Deny Lists**: No regex soup. Clear, maintainable role filtering.

5. **Email Confidence Matters**: Don't use `potential_emails` blindly. Generate with confidence scores.

6. **Track Rejections**: Always save rejected rows with reasons. This is how you improve.

7. **No NLP Yet**: This is a structural problem, not semantic. NLP comes after clean schema, stable personas, and valid email infra.

---

## What Changed

### Before:
- Raw scraping output → Direct scoring → Staging
- No hard filtering
- No role qualification
- No title normalization
- Email from `potential_emails` directly
- No rejection tracking

### After:
- Raw scraping output → **Normalization Layer** → Scoring → Staging
- Hard filtering of invalid profiles
- Explicit role allow/deny lists
- Title normalization to canonical roles
- Email generation with confidence scores
- Rejection tracking with reasons

---

## Next Steps

1. **Test with Zepto data**: Run the pipeline and verify conversion rates
2. **Review rejected_debug.csv**: Understand why leads were dropped
3. **Tune allow/deny lists**: Adjust based on actual outreach needs
4. **Email verification**: Add SMTP/API verification for low-confidence emails
5. **Performance tracking**: Track open/reply rates by normalized role

---

## Files

- `normalize_for_outreach.py`: Core normalization logic
  - Uses `logging` module for all output (no print statements)
  - Implements minimum email confidence threshold (0.3)
  - Captures rejection reasons for all filtered leads
  - Includes catch-all IC role normalization

- `staffspy_ingest.py`: Main pipeline (now uses normalization)
  - Organized diagnostics directory structure
  - Company-specific folders for all output files
  - Path: `scraper_bridge/diagnostics/company_snapshots/{company}/`

- `NORMALIZATION_ARCHITECTURE.md`: This document

## Directory Structure

```
scraper_bridge/
├── normalize_for_outreach.py
├── staffspy_ingest.py
├── diagnostics/
│   └── company_snapshots/
│       ├── zepto/
│       │   ├── staffspy_raw_snapshot.csv
│       │   ├── staffspy_outreach_ready.csv
│       │   └── staffspy_rejected_debug.csv
│       ├── company2/
│       │   └── ...
│       └── ...
└── NORMALIZATION_ARCHITECTURE.md
```

---

## Questions?

The normalization layer is **the business logic** that transforms scraping output into outreach-ready data. It enforces strict data contracts and ensures only high-quality, actionable leads proceed in the pipeline.

