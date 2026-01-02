import pandas as pd
import os

# =========================
# CONFIGURATION
# =========================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

INPUT_CSV = os.path.join(SCRIPT_DIR, 'final_verified_leads.csv')
OUTPUT_CSV = os.path.join(PROJECT_ROOT, 'data', 'processed', 'cold_email_outreach_all_cleaned_ranked.csv')

SOURCE_NAME = 'qualified_pipeline'

# =========================
# SCHEMA ENFORCER
# =========================

def enforce_master_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converts a verified leads dataframe into campaign-ready master schema.
    Safe, deterministic, idempotent.
    """

    defaults = {
        'Location': '',
        'Source': SOURCE_NAME,
        'Sent_Status': 'PENDING',
        'Sent_Timestamp': '',
        'FollowUp_1_Status': '',
        'FollowUp_1_Timestamp': '',
        'FollowUp_2_Status': '',
        'FollowUp_2_Timestamp': ''
    }

    # Ensure required base columns exist
    required_base = ['Name', 'Title', 'Email', 'Company', 'HiringScore']
    for col in required_base:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # Add missing campaign columns
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    # Normalize types
    df['HiringScore'] = df['HiringScore'].astype(int)
    df['Email'] = df['Email'].astype(str).str.strip().str.lower()

    # Canonical column order
    ordered_columns = [
        'Name',
        'Title',
        'Email',
        'Company',
        'Location',
        'Source',
        'HiringScore',
        'Sent_Status',
        'Sent_Timestamp',
        'FollowUp_1_Status',
        'FollowUp_1_Timestamp',
        'FollowUp_2_Status',
        'FollowUp_2_Timestamp'
    ]

    return df[ordered_columns]

# =========================
# PIPELINE
# =========================

def main():
    if not os.path.exists(INPUT_CSV):
        raise FileNotFoundError(f"Input file not found: {INPUT_CSV}")

    print("▶ Loading verified leads…")
    df = pd.read_csv(INPUT_CSV)
    original_len = len(df)

    print("▶ Enforcing master campaign schema…")
    df_master = enforce_master_schema(df)

    print("▶ Saving campaign-ready master CSV…")
    df_master.to_csv(OUTPUT_CSV, index=False)

    print("—" * 50)
    print(f"✔ Records ingested: {len(df_master)}")
    print(f"📁 Output: {OUTPUT_CSV}")
    print("✔ Ready for outreach/campaign.py")

# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    main()