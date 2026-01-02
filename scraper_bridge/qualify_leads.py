import pandas as pd
import os
import re
import dns.resolver  # pip install dnspython
from functools import lru_cache

# --- CONFIGURATION ---
# Have ahia full path api didho che etle error nahi ave
INPUT_CSV = '/Users/vaibhavsingh/coldemail/scraper_bridge/converted_it_companies_deduplicated.csv'
OUTPUT_CSV = '/Users/vaibhavsingh/coldemail/scraper_bridge/final_verified_leads.csv'

# --- CONSTANTS ---
ROLE_PREFIXES = {
    'info', 'support', 'sales', 'admin', 'help', 'career', 'careers', 
    'hr', 'team', 'contact', 'marketing', 'hello', 'jobs', 'billing'
}

FREE_DOMAINS = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 
    'aol.com', 'icloud.com', 'live.com', 'rediffmail.com'
}

# Regex for basic email syntax
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# --- ENGINES ---

@lru_cache(maxsize=4096)
def check_mx_record(domain):
    """Checks if the domain has a valid mail server (MX record)."""
    try:
        dns.resolver.resolve(domain, 'MX')
        return True
    except:
        return False

def check_name_email_match(name, email):
    """Bonuses if 'Rahul' is in 'rahul@company.com'."""
    if pd.isna(name) or pd.isna(email): return 0
    name_parts = [p for p in str(name).lower().split() if len(p) > 2]
    email_user = email.split('@')[0].lower()
    return 10 if any(part in email_user for part in name_parts) else 0

def qualify_lead(row):
    """Scoring Logic: Syntax -> Role -> Domain -> MX -> Authority."""
    email = str(row['Email']).strip().lower()
    title = str(row.get('Title', '')).lower()
    name = str(row.get('Name', ''))
    
    # 1. Syntax (Fail Fast)
    if not EMAIL_REGEX.match(email):
        return {'status': 'INVALID_SYNTAX', 'score': 0}

    user_part, domain_part = email.split('@')

    # 2. Role Check
    if user_part in ROLE_PREFIXES:
        return {'status': 'LOW_QUALITY_ROLE', 'score': 5}

    # 3. Domain Authority
    if domain_part in FREE_DOMAINS:
        base_score = 10 # Public domain
    else:
        base_score = 30 # Corporate domain

    # 4. Consistency Bonus
    bonus = check_name_email_match(name, email)

    # 5. Title Authority
    title_score = 0
    if any(t in title for t in ['ceo', 'cto', 'cio', 'founder', 'md', 'president']):
        title_score = 40
    elif any(t in title for t in ['vp', 'director', 'head']):
        title_score = 30
    elif any(t in title for t in ['hr', 'talent', 'hiring', 'recruiter']):
        title_score = 25
    elif any(t in title for t in ['manager', 'lead']):
        title_score = 10

    # 6. Data Completeness
    data_score = 0
    if len(name) > 2: data_score += 10
    if len(str(row.get('Company', ''))) > 2: data_score += 10

    total = min(100, base_score + bonus + title_score + data_score)
    return {'status': 'VERIFIED', 'score': total}

# --- PIPELINE ---

def run_pipeline():
    if not os.path.exists(INPUT_CSV):
        print(f"Error: {INPUT_CSV} not found.")
        return

    print("Step 1: Loading Data...")
    df = pd.read_csv(INPUT_CSV)
    original_len = len(df)
    
    # Drop empty emails immediately
    df = df[df['Email'].notna()].copy()

    print("Step 2: Scoring & Filtering...")
    results = df.apply(qualify_lead, axis=1)
    df['Quality_Status'] = results.apply(lambda x: x['status'])
    df['HiringScore'] = results.apply(lambda x: x['score'])

    # Remove invalid syntax/blocked immediately
    df_clean = df[~df['Quality_Status'].str.startswith('INVALID')]
    
    print("Step 3: Verifying DNS (Network Check)...")
    # Only check unique corporate domains to save time
    unique_domains = df_clean[df_clean['HiringScore'] > 15]['Email'].apply(lambda x: x.split('@')[-1]).unique()
    valid_domains = set()
    
    for i, d in enumerate(unique_domains):
        if check_mx_record(d): valid_domains.add(d)
        if i % 100 == 0: print(f"  Verified {i} domains...")

    # Apply MX filter (Keep public domains + valid corporate domains)
    df_clean['domain'] = df_clean['Email'].apply(lambda x: x.split('@')[-1])
    df_final = df_clean[
        (df_clean['domain'].isin(FREE_DOMAINS)) | 
        (df_clean['domain'].isin(valid_domains))
    ].copy()
    
    # Sort best leads to top
    df_final = df_final.sort_values(by='HiringScore', ascending=False)
    
    # Save
    cols = ['Name', 'Title', 'Company', 'Email', 'HiringScore', 'Quality_Status']
    final_cols = [c for c in cols if c in df_final.columns]
    df_final[final_cols].to_csv(OUTPUT_CSV, index=False)
    
    print("-" * 30)
    print(f"Complete. {len(df_final)} verified leads saved to {OUTPUT_CSV}")
    print(f"Dropped {original_len - len(df_final)} bad records.")

if __name__ == "__main__":
    run_pipeline()