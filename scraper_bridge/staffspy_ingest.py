import os
import pandas as pd
import time
import random
import logging
import ast
from staffspy import LinkedInAccount
from dotenv import load_dotenv
from normalize_for_outreach import normalize_for_outreach # Assuming this is your separate file

# --- I. CONFIGURATION AND SETUP ---
load_dotenv()

# Resolve log file path safely
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "staffspy_ingest_log.txt")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logging.info("--- Starting new StaffSpy Ingestion Run ---")

MIN_SLEEP = 3
MAX_SLEEP = 8

# --- RUN MODES ---
# SAFE MODE: real scraping, but limited to one company and no file writes
SAFE_SINGLE_COMPANY_MODE = True
SAFE_COMPANY_NAME = "Zepto"  # change as needed

# FULL PRODUCTION MODE
PRODUCTION_MODE = False


# --- I-B. PATHS AND DIRECTORY SETUP ---
# PROJECT_ROOT is assumed to be the directory one level above SCRIPT_DIR
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Diagnostics files now live inside SCRIPT_DIR (scraper_bridge/)
DIAGNOSTICS_BASE_DIR = os.path.join(SCRIPT_DIR, "diagnostics", "company_snapshots")
os.makedirs(DIAGNOSTICS_BASE_DIR, exist_ok=True) # Create the base directories if they don't exist
logging.info(f"Diagnostic files will be organized under: {DIAGNOSTICS_BASE_DIR}")


MASTER_CSV_FOR_DEDUP = os.path.join(
    PROJECT_ROOT, "cold_email_outreach_all_cleaned_ranked.csv.backup"
)
# MODIFIED: Staging file now points to SCRIPT_DIR
NEW_LEADS_CSV_STAGING = os.path.join(
    SCRIPT_DIR, "staffspy_new_leads_staging.csv"
)
TARGET_COMPANIES_FILE = os.path.join(
    PROJECT_ROOT, "target_companies.csv"
)

# --- TARGET TITLES ---
TARGET_TITLES = [
    "Founder", "Co-Founder", "Chief Executive Officer",
    "Chief Technology Officer", "Chief Product Officer",
    "Founder's Office", "Chief of Staff", "Head of Special Projects",
    "VP of Engineering", "Director of Engineering", "Head of Engineering",
    "Engineering Manager", "Tech Lead", "Lead Software Engineer",
    "Head of Platform Engineering", "Head of Infrastructure",
    "Head of AI", "Applied Scientist", "ML Platform Engineer",
    "Head of Data Science", "Lead Data Scientist",
    "VP of Product", "Product Manager",
    "Chief People Officer", "Technical Recruiting Manager"
]

# Normalize for consistent matching (fixes case sensitivity issues)
TARGET_TITLES = [t.lower() for t in TARGET_TITLES]

# ----------------------------------------------------
# II. SCORING + HELPERS (UNCHANGED)
# ----------------------------------------------------

# NOTE: The helper functions are included below for completeness
def extract_primary_email(val):
    """Extract first email from potential_emails string (which is a stringified list)."""
    if pd.isna(val) or val == "":
        return None
    try:
        # Handle stringified list like "['email1@company.com', 'email2@company.com']"
        emails = ast.literal_eval(str(val))
        if isinstance(emails, list) and emails:
            return emails[0].strip()
        return None
    except (ValueError, SyntaxError, TypeError):
        # If it's already a string email, return it
        val_str = str(val).strip()
        if "@" in val_str:
            return val_str
        return None


def safe_int(value, default=0):
    """Safely convert to int, handling pd.NA and None."""
    if pd.isna(value) or value is None:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def safe_bool(value, default=False):
    """Safely convert to bool, handling pd.NA."""
    if pd.isna(value) or value is None:
        return default
    try:
        return bool(value)
    except (ValueError, TypeError):
        return default


def staffspy_hiring_score(row):
    """Calculate hiring score with safe pandas NA handling."""
    score = 0

    title = str(row.get("Title", "")).lower()
    skills = str(row.get("Skills_StaffSpy", "")).lower()
    experience = str(row.get("Experience_StaffSpy", "")).lower()

    if any(k in title for k in ["founder", "co-founder", "ceo", "cto", "cpo"]):
        score += 45
    elif any(k in title for k in ["vp", "head", "director"]):
        score += 35
    elif any(k in title for k in ["manager", "lead"]):
        score += 20

    if any(k in skills for k in [
        "machine learning", "ml", "ai", "deep learning",
        "distributed", "systems", "infrastructure", "platform"
    ]):
        score += 30

    if any(k in experience for k in ["founder", "scaling", "platform", "infra"]):
        score += 15

    # SAFE: Handle pandas NA properly
    followers = safe_int(row.get("Followers"), 0)
    if followers >= 1000:
        score += 10

    is_hiring = safe_bool(row.get("Is_Hiring"), False)
    if is_hiring:
        score += 10

    return min(score, 100)


def load_target_companies(path):
    """
    Loads target companies from CSV.
    Required columns:
        - Company Name
        - Estimated Email Format
    """
    try:
        df = pd.read_csv(path)

        required_cols = ["Company Name", "Estimated Email Format"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        records = df.to_dict(orient="records")
        logging.info(f"Loaded {len(records)} companies from CSV")
        return records

    except Exception as e:
        logging.error(f"Failed loading companies CSV: {e}")
        return []


def update_target_companies_file(companies_data, path):
    """Saves the remaining list of company dictionaries back to the CSV."""
    if companies_data:
        try:
            df = pd.DataFrame(companies_data)
            df.to_csv(path, index=False)
            logging.info(f"💾 PRODUCTION: Updated target companies CSV with {len(df)} remaining records.")
        except Exception as e:
            logging.error(f"❌ FATAL: Could not save updated target companies CSV: {e}")


def filter_invalid_profiles(df):
    """Hard filter: Remove garbage rows (headless profiles, invalid data)."""
    initial_count = len(df)
    
    # Filter conditions for invalid profiles
    invalid_conditions = (
        df["profile_id"].isna()
        | (df["profile_id"] == "headless")
        | (df["profile_id"].astype(str).str.contains("headless", case=False, na=False))
        | (df["profile_link"].astype(str).str.contains("search/results", case=False, na=False))
        | (df["name"].astype(str).str.contains("LinkedIn Member", case=False, na=False))
    )
    
    df_clean = df[~invalid_conditions].copy()
    removed = initial_count - len(df_clean)
    
    if removed > 0:
        logging.info(f"FILTERED: Removed {removed} invalid/garbage profiles ({initial_count} → {len(df_clean)})")
    
    return df_clean


def apply_outreach_quality_filters(df):
    """Apply strict filters for outreach-ready leads only."""
    initial_count = len(df)
    
    # Title keywords that indicate actionable roles
    TITLE_KEYWORDS = [
        "engineer", "engineering", "sde", "developer",
        "manager", "lead", "director", "vp", "head",
        "founder", "co-founder", "cto", "cpo", "ceo"
    ]
    
    # Build filter conditions - check both headline/position columns if they exist
    has_relevant_title = pd.Series([False] * len(df), index=df.index)
    
    if "headline" in df.columns:
        has_relevant_title = has_relevant_title | df["headline"].astype(str).str.contains(
            "|".join(TITLE_KEYWORDS), case=False, na=False
        )
    if "position" in df.columns:
        has_relevant_title = has_relevant_title | df["position"].astype(str).str.contains(
            "|".join(TITLE_KEYWORDS), case=False, na=False
        )
    if "Title" in df.columns:
        has_relevant_title = has_relevant_title | df["Title"].astype(str).str.contains(
            "|".join(TITLE_KEYWORDS), case=False, na=False
        )
    
    has_email = df["Email"].notna() & (df["Email"].astype(str).str.strip() != "")
    
    # FIX: Remove follower gating - followers belong in scoring, not filtering
    # This prevents dropping good leads (mid-level engineers, senior ICs) before scoring
    has_min_followers = pd.Series([True] * len(df), index=df.index)
    
    # Apply all filters
    df_filtered = df[
        has_relevant_title
        & has_email
        & has_min_followers
    ].copy()
    
    removed = initial_count - len(df_filtered)
    if removed > 0:
        logging.info(
            f"OUTREACH FILTER: {removed} leads removed, {len(df_filtered)} outreach-ready leads remain"
        )
    
    return df_filtered


def data_audit(df):
    """Final data quality audit on cleaned data."""
    logging.info("--- Starting Data Quality Audit ---")

    missing_email = (df["Email"].isna() | (df["Email"] == "")).sum()
    if missing_email > 0:
        logging.error(f"CRITICAL: {missing_email} leads missing email (should be 0 after filtering)")

    if "Title" in df.columns:
        missing = df["Title"].isna().sum()
        if missing:
            logging.warning(f"{missing} leads missing title")

    if "LinkedIn_URL" in df.columns:
        missing = df["LinkedIn_URL"].isna().sum()
        if missing:
            logging.warning(f"{missing} leads missing LinkedIn URL")

    logging.info(f"Audit complete. {len(df)} usable leads.")
    return df


def generate_email_from_pattern(first, last, pattern):
    if not first or not last or not pattern or pd.isna(pattern):
        return ""

    first = str(first).strip().lower()
    last = str(last).strip().lower()

    return (
        pattern
        .replace("{first}", first)
        .replace("{last}", last)
        .replace("{f}", first[0])
        .replace("{l}", last[0])
    )


# ----------------------------------------------------
# III. MAIN PIPELINE
# ----------------------------------------------------

def scrape_and_stage_new_leads():

    if not (SAFE_SINGLE_COMPANY_MODE or PRODUCTION_MODE):
        logging.critical("No run mode enabled. Set SAFE_SINGLE_COMPANY_MODE or PRODUCTION_MODE.")
        return

    account = LinkedInAccount(
        username=os.getenv("LINKEDIN_EMAIL"),
        password=os.getenv("LINKEDIN_PASSWORD"),
        session_file="staffspy_session.pkl",
        log_level=1
    )

    if SAFE_SINGLE_COMPANY_MODE:
        # FIX: Load email format from CSV instead of hardcoding empty string
        all_companies = load_target_companies(TARGET_COMPANIES_FILE)
        companies = [
            c for c in all_companies
            if c.get("Company Name", "").lower() == SAFE_COMPANY_NAME.lower()
        ]
        if not companies:
            logging.error(f"SAFE MODE company '{SAFE_COMPANY_NAME}' not found in CSV")
            return
        logging.info(f"SAFE MODE: Using email format '{companies[0].get('Estimated Email Format', 'N/A')}' for {SAFE_COMPANY_NAME}")
    else:
        companies = load_target_companies(TARGET_COMPANIES_FILE)
        if not companies:
            logging.warning("No companies to scrape")
            return

    seen_profiles = set()

    new_leads_data = []

    for entry in companies:
        company = entry.get("Company Name")
        email_format = entry.get("Estimated Email Format", "")
        company_lower = company.lower().replace(" ", "_") # Sanitize company name for folder path

        # --- NEW: Create company-specific diagnostics directory inside SCRIPT_DIR ---
        COMPANY_DIAGNOSTICS_DIR = os.path.join(DIAGNOSTICS_BASE_DIR, company_lower)
        os.makedirs(COMPANY_DIAGNOSTICS_DIR, exist_ok=True)
        # -----------------------------------------------------------

        sleep = random.uniform(MIN_SLEEP, MAX_SLEEP)
        time.sleep(sleep)

        try:
            df = account.scrape_staff(
                company_name=company,
                search_term="engineering",  # broad search term
                extra_profile_data=True,
                max_results=300
            )

            # --- STEP 1: Save raw snapshot for inspection ---
            # PATH CHANGE: Use company-specific folder and generic filename
            raw_snapshot_path = os.path.join(
                COMPANY_DIAGNOSTICS_DIR, "staffspy_raw_snapshot.csv"
            )
            df.to_csv(raw_snapshot_path, index=False)
            logging.info(f"💾 Saved raw StaffSpy snapshot ({len(df)} rows) to {raw_snapshot_path}")

            # --- STEP 2: NORMALIZE FOR OUTREACH (the critical business logic layer) ---
            outreach_df, rejected_df = normalize_for_outreach(
                raw_df=df,
                company_name=company,
                email_format=email_format
            )
            
            if outreach_df.empty:
                logging.warning(f"{company}: No outreach-ready leads after normalization")
                # Still save rejected debug for analysis
                if not rejected_df.empty:
                    # PATH CHANGE: Use company-specific folder and generic filename
                    rejected_path = os.path.join(
                        COMPANY_DIAGNOSTICS_DIR, "staffspy_rejected_debug.csv"
                    )
                    rejected_df.to_csv(rejected_path, index=False)
                    logging.info(f"💾 Saved rejected debug ({len(rejected_df)} rows) to {rejected_path}")
                continue
            
            # --- STEP 3: Save outreach-ready CSV (strict schema) ---
            # PATH CHANGE: Use company-specific folder and generic filename
            outreach_path = os.path.join(
                COMPANY_DIAGNOSTICS_DIR, "staffspy_outreach_ready.csv"
            )
            outreach_df.to_csv(outreach_path, index=False)
            logging.info(f"✅ Saved outreach-ready CSV ({len(outreach_df)} rows) to {outreach_path}")
            
            # --- STEP 3b: Save rejected debug file ---
            if not rejected_df.empty:
                # PATH CHANGE: Use company-specific folder and generic filename
                rejected_path = os.path.join(
                    COMPANY_DIAGNOSTICS_DIR, "staffspy_rejected_debug.csv"
                )
                rejected_df.to_csv(rejected_path, index=False)
                logging.info(f"💾 Saved rejected debug ({len(rejected_df)} rows) to {rejected_path}")
            
            # --- STEP 4: Convert normalized outreach data to legacy format for scoring/staging ---
            # (This maintains compatibility with existing scoring/staging logic)
            for _, row in outreach_df.iterrows():
                profile_id = row.get("profile_id", "")
                if profile_id and profile_id in seen_profiles:
                    continue
                if profile_id:
                    seen_profiles.add(profile_id)
                
                # Extract skills text from preserved raw data
                skills_text = ""
                skills_raw = row.get("skills", "")
                if skills_raw and not pd.isna(skills_raw):
                    try:
                        skills_list = ast.literal_eval(str(skills_raw)) if isinstance(skills_raw, str) and skills_raw.startswith("[") else []
                        if isinstance(skills_list, list):
                            skills_text = ", ".join([str(s) for s in skills_list[:10]])
                    except:
                        skills_text = str(skills_raw)
                
                # Extract experience text
                experience_text = row.get("headline", "")
                experiences_raw = row.get("experiences", "")
                if experiences_raw and not pd.isna(experiences_raw):
                    experience_text = str(experiences_raw)[:200]  # Truncate
                
                # Map normalized schema to legacy format for scoring
                new_leads_data.append({
                    "Name": f"{row.get('first_name', '')} {row.get('last_name', '')}".strip(),
                    "Title": row.get("role", "N/A"),
                    "Email": row.get("email", ""),
                    "Company": company,
                    "LinkedIn_URL": row.get("linkedin_url", ""),
                    "Skills_StaffSpy": skills_text,
                    "Experience_StaffSpy": experience_text,
                    "Followers": safe_int(row.get("followers"), 0),
                    "Connections": safe_int(row.get("connections"), 0),
                    "Is_Hiring": safe_bool(row.get("is_hiring"), False),
                    "headline": row.get("headline", ""),
                    "position": row.get("role", ""),  # Use normalized role
                    # Add normalized fields for future use
                    "Seniority": row.get("seniority", ""),
                    "Department": row.get("department", ""),
                    "Email_Confidence": row.get("email_confidence", 0.0)
                })

        except Exception as e:
            logging.warning(f"{company}: {e}")

        if not SAFE_SINGLE_COMPANY_MODE:
            # Get the company name of the successfully processed entry
            processed_company_name = entry.get("Company Name")
            
            # Use list comprehension to create the list of *remaining* companies
            # This is safer than modifying the list being iterated over
            companies = [c for c in companies if c.get("Company Name") != processed_company_name]
            
            # Save the new, shorter list back to the CSV
            update_target_companies_file(companies, TARGET_COMPANIES_FILE)

    logging.info(f"Collected {len(new_leads_data)} leads after initial processing")

    # ----------------------------------------------------
    # STEP 3: OUTREACH-QUALITY FILTERING (Continues with legacy steps)
    # ----------------------------------------------------

    new_df = pd.DataFrame(new_leads_data)

    # --- SAFETY: handle empty scrape results ---
    if new_df.empty:
        logging.warning(
            "No leads collected AFTER PROCESSING. "
            "Check the diagnostics directory to inspect raw data."
        )
        snapshot_path = os.path.join(SCRIPT_DIR, "staffspy_test_snapshot_empty.csv")
        new_df.to_csv(snapshot_path, index=False)
        logging.info(f"Saved empty snapshot to {snapshot_path}")
        return

    # --- STEP 4: Post-normalization validation (normalization already did all filtering) ---
    # Just ensure emails exist (normalization guarantees this, but double-check for safety)
    if "Email" in new_df.columns:
        new_df = new_df[new_df["Email"].notna() & (new_df["Email"].astype(str).str.strip() != "")]
    
    if new_df.empty:
        logging.warning("No outreach-ready leads after normalization")
        return

    # --- ENFORCE EXPECTED SCHEMA ---
    EXPECTED_COLUMNS = [
        "Name", "Title", "Email", "Company", "LinkedIn_URL",
        "Skills_StaffSpy", "Experience_StaffSpy",
        "Followers", "Connections", "Is_Hiring"
    ]

    for col in EXPECTED_COLUMNS:
        if col not in new_df.columns:
            new_df[col] = pd.NA

    # --- STEP 5: Deduplication ---
    if os.path.exists(MASTER_CSV_FOR_DEDUP):
        master_df = pd.read_csv(MASTER_CSV_FOR_DEDUP)
        existing_emails = (
            master_df["Email"]
            .dropna()
            .astype(str)
            .str.lower()
            .tolist()
        )
    else:
        existing_emails = []

    if "Email" in new_df.columns:
        new_df = new_df[
            ~new_df["Email"].astype(str).str.lower().isin(existing_emails)
        ]
    else:
        logging.warning("Email column missing; skipping deduplication step.")

    # --- STEP 6: Final audit ---
    new_df = data_audit(new_df)

    if new_df.empty:
        logging.info("No new leads after audit")
        return

    # --- STEP 7: Calculate HiringScore (with safe NA handling) ---
    new_df["HiringScore"] = new_df.apply(
        staffspy_hiring_score, axis=1
    )

    new_df["Confidence"] = new_df["HiringScore"].apply(
        lambda x: 3 if x >= 70 else 2 if x >= 40 else 1
    )

    # --- STEP 8: Final cleanup - remove temporary columns ---
    columns_to_drop = ["headline", "position"]
    for col in columns_to_drop:
        if col in new_df.columns:
            new_df = new_df.drop(columns=[col])

    new_df["Source"] = "LinkedIn_StaffSpy"
    new_df["Location"] = pd.NA  # Will be filled later if needed
    new_df["Sent_Status"] = "PENDING"
    new_df["Sent_Timestamp"] = ""
    new_df["FollowUp_1_Status"] = "PENDING"
    new_df["FollowUp_1_Timestamp"] = ""
    new_df["FollowUp_2_Status"] = "PENDING"
    new_df["FollowUp_2_Timestamp"] = ""

    # --- STEP 9: Save results ---
    if PRODUCTION_MODE:
        new_df.to_csv(NEW_LEADS_CSV_STAGING, index=False)
        logging.info(f"✅ PRODUCTION: Saved {len(new_df)} outreach-ready leads to staging CSV at {NEW_LEADS_CSV_STAGING}")
    else:
        # SAFE MODE: write to snapshot file for evaluation
        snapshot_path = os.path.join(SCRIPT_DIR, "staffspy_test_snapshot.csv")
        new_df.to_csv(snapshot_path, index=False)
        logging.info(
            f"✅ SAFE MODE: Saved test results snapshot ({len(new_df)} outreach-ready leads) to {snapshot_path}"
        )
        print(f"\n✅ Test complete: {len(new_df)} outreach-ready leads saved to {snapshot_path}")

    # --- FINAL SUMMARY ---
    print("\n" + "="*70)
    print("PIPELINE SUMMARY")
    print("="*70)
    print(f"✅ Outreach-ready leads: {len(new_df)}")
    print(f"📊 Average HiringScore: {new_df['HiringScore'].mean():.1f}")
    print(f"📧 Leads with emails: {new_df['Email'].notna().sum()}")
    print(f"🎯 High-score leads (≥70): {(new_df['HiringScore'] >= 70).sum()}")
    print("="*70)
    print(f"\nCheck logs and output file for details.")


if __name__ == "__main__":
    scrape_and_stage_new_leads()