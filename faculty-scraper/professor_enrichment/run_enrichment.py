# coldemail/faculty-scraper/professor_enrichment/run_enrichment.py

import pandas as pd
import time
import random
import sys
import os

from .config import (
    DATA_DIR,
    BASE_SLEEP_TIME,
    MODE,
    TEST_ROW_LIMIT,
    SAVE_EVERY_N_ROWS,
)
from .scraper import scrape_and_process_profile
from .utils.data_loader import list_university_csvs, get_csv_path


# ----------------------------
# UTILS
# ----------------------------

def safe_save_csv(df, path):
    df.to_csv(path, index=False)


def ask_rerun_confirmation(done_count):
    choice = input(
        f"\nFound {done_count} already-scraped profiles.\n"
        "Do you want to re-run them? (y/N): "
    ).strip().lower()
    return choice == "y"


def ask_csv_selection(csv_files):
    """
    Prompts user to select which CSV files to process.
    """
    if not csv_files:
        print("ERROR: No CSV files found in data directory.")
        return []
    
    print("\nAvailable universities:\n")
    for i, csv_file in enumerate(csv_files, 1):
        csv_name = csv_file.replace('.csv', '')
        print(f"{i}) {csv_name}")
    
    choice = input(
        "\nSelect universities to run (e.g. 1,3 or 'all'): "
    ).strip().lower()
    
    if choice == "all" or choice == "":
        return csv_files
    
    try:
        indices = [int(x.strip()) - 1 for x in choice.split(",")]
        selected = [csv_files[i] for i in indices if 0 <= i < len(csv_files)]
        return selected if selected else csv_files
    except (ValueError, IndexError):
        print(f"Invalid selection. Processing all files.")
        return csv_files


def detect_university_from_url(url):
    url = (url or "").lower()
    if "ucla.edu" in url:
        return "ucla"
    if "berkeley.edu" in url:
        return "berkeley"
    if "illinois.edu" in url:
        return "uiuc"
    if "harvard.edu" in url:
        return "harvard"
    return "other"
    
# NEW HELPER: Detect university from CSV name
def detect_university_from_csv_name(csv_name):
    return csv_name.replace('.csv', '').lower()

# NEW HARVARD GENERATION LOGIC - ***CORRECTED SLUG GENERATION***
def generate_harvard_url_from_name(name: str) -> str | None:
    if not name or not isinstance(name, str):
        return None

    # Step 1: Clean punctuation and split into parts
    parts = (
        name.replace(".", "") # Remove Michael J. Aziz -> Michael J Aziz
        .replace(",", "")
        .split()
    )

    # Step 2: Drop middle initials (tokens with length 1, e.g., 'J' or 'P')
    # and ensure it has enough parts (e.g., handles "Dr. Michael" correctly)
    parts = [p for p in parts if len(p) > 1] 

    if len(parts) < 2:
        # Must have at least a first and last name remaining
        return None

    # Step 3: Get the first name and the last name
    first = parts[0].lower()
    last = parts[-1].lower()

    # Result: michael-aziz
    return f"https://seas.harvard.edu/person/{first}-{last}"

def ensure_harvard_profile_links(df: pd.DataFrame) -> pd.DataFrame:
    """
    Creates/fills the 'PROFILE LINK' column for Harvard profiles based on NAME.
    """
    if "PROFILE LINK" not in df.columns:
        df["PROFILE LINK"] = pd.NA

    # Identify rows where the link is missing or just whitespace
    missing_mask = df["PROFILE LINK"].isna() | (df["PROFILE LINK"].astype(str).str.strip() == "")

    filled = 0
    # Use iterrows for precise index tracking and safe loc assignment
    for idx, row in df[missing_mask].iterrows():
        name = row.get("NAME")
        if not name:
            continue

        url = generate_harvard_url_from_name(name)
        if url:
            df.loc[idx, "PROFILE LINK"] = url
            filled += 1

    print(f"✓ Generated PROFILE LINK for {filled} Harvard profiles")
    return df


# ----------------------------
# SINGLE CSV PROCESSING
# ----------------------------

def run_single_csv(csv_path, csv_name):
    """
    Processes a single CSV file through the enrichment pipeline.
    """
    print(f"\n{'='*70}")
    print(f"Running enrichment for {csv_name}")
    print(f"{'='*70}")
    
    try:
        df = pd.read_csv(csv_path)
        print(f"Loaded {len(df)} rows from {csv_name}")
    except FileNotFoundError:
        print(f"ERROR: File not found: {csv_path}")
        return
    except Exception as e:
        print(f"ERROR: Failed to load {csv_name}: {e}")
        return

    university_type = detect_university_from_csv_name(csv_name)

    # ----------------------------
    # HARVARD DATA PREP PHASE (Fix for missing URLs)
    # ----------------------------
    if university_type == "harvard":
        # The pandas dataframe must have a 'PROFILE LINK' column now.
        if 'PROFILE LINK' not in df.columns:
             df['PROFILE LINK'] = pd.NA # Ensure column exists before prep

        # This call uses the newly fixed, correct slug generation logic
        df = ensure_harvard_profile_links(df)
        safe_save_csv(df, csv_path) # Persist the generated URLs immediately
        
    # Add University column if missing (now relies on the filled URL)
    if 'University' not in df.columns:
        # Using the scraper's detection method for consistency
        df['University'] = df['PROFILE LINK'].apply(detect_university_from_url)

    # Initialize required columns
    new_cols = [
        'Primary_Focus',
        'Source_Sentence',
        'Research_Question_Hint',
        'Personalization_Line',
        'Email_Subject',
        'HiringScore',
        'Confidence',
        'Research_Areas',
        'Domain',
        'Scrape_Status',
        'Error_Detail',
    ]

    for c in new_cols:
        if c not in df.columns:
            df[c] = pd.NA

    # ----------------------------
    # SKIP / RERUN LOGIC
    # ----------------------------

    success_mask = df['Scrape_Status'].fillna("").str.startswith("SUCCESS")
    success_count = success_mask.sum()

    rerun = False
    if success_count > 0:
        rerun = ask_rerun_confirmation(success_count)

    if rerun:
        rows = df
    else:
        rows = df.loc[~success_mask]

    if rows.empty:
        print(f"No rows to process for {csv_name}. Skipping.")
        return

    if MODE == "TEST":
        rows = rows.head(TEST_ROW_LIMIT)

    print(f"\nStarting scraping ({len(rows)} rows)\n")

    # ----------------------------
    # SCRAPING LOOP
    # ----------------------------

    processed = 0

    for idx, row in rows.iterrows():
        processed += 1
        name = row.get('NAME', 'UNKNOWN')

        print(f"→ Processing ({processed}/{len(rows)}): {name}")

        # The scraper.py code now ASSUMES a valid URL is in 'PROFILE LINK'
        result = scrape_and_process_profile(row)

        for k, v in result.items():
            if k in df.columns:
                df.loc[idx, k] = v

        # Periodic save
        if processed % SAVE_EVERY_N_ROWS == 0:
            safe_save_csv(df, csv_path)
            print("✓ Intermediate save")

        time.sleep(BASE_SLEEP_TIME + random.uniform(0.5, 1.5))

    # ----------------------------
    # SENT STATUS LOGIC
    # ----------------------------

    if 'Sent_Status' not in df.columns:
        df['Sent_Status'] = 'NEEDS REVIEW'

    df.loc[rows.index, 'Sent_Status'] = 'NEEDS REVIEW'
    df.loc[
        (df.index.isin(rows.index))
        & (df['Scrape_Status'] == 'SUCCESS')
        & (df['Confidence'] >= 1),
        'Sent_Status'
    ] = 'PENDING'

    # Final save
    safe_save_csv(df, csv_path)

    print("\n" + "=" * 70)
    print(f"SUCCESS: Enrichment finished for {csv_name} ({len(rows)} rows)")
    print("=" * 70)

    print("\nSummary:")
    try:
        print(
            df.loc[rows.index, [
                'NAME',
                'Scrape_Status',
                'Confidence',
                'HiringScore',
                'Sent_Status',
            ]].to_string(index=False)
        )
    except Exception as e:
        print(f"Could not display summary: {e}")


# ----------------------------
# MAIN ORCHESTRATION
# ----------------------------

def run_enrichment():
    """Main function that orchestrates the multi-CSV enrichment process."""
    print(f"DEBUG: DATA_DIR = {DATA_DIR}")
    print(f"DEBUG: MODE = {MODE}")
    
    # Scan for available CSV files
    csv_files = list_university_csvs(DATA_DIR)
    
    if not csv_files:
        print(f"ERROR: No CSV files found in {DATA_DIR}")
        return
    
    # Prompt user to select which CSVs to process
    selected_csvs = ask_csv_selection(csv_files)
    
    if not selected_csvs:
        print("No CSV files selected. Exiting.")
        return
    
    print(f"\nSelected {len(selected_csvs)} CSV file(s) to process.")
    
    # Process each selected CSV
    for csv_name in selected_csvs:
        csv_path = get_csv_path(DATA_DIR, csv_name)
        run_single_csv(csv_path, csv_name)
    
    print("\n" + "=" * 70)
    print("ALL ENRICHMENT RUNS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    try:
        run_enrichment()
    except Exception as e:
        print(f"FATAL: {e}")
        sys.exit(1)