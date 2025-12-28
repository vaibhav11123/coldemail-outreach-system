import pandas as pd
import os
from typing import List, Dict, Any

# Define the relative path to the master CSV file
MASTER_CSV_PATH = '../cold_email_outreach_all_cleaned_ranked.csv'

def ingest_new_leads(
    new_leads: List[Dict[str, Any]],
    csv_file_path: str = MASTER_CSV_PATH
) -> None:
    """
    Appends new, non-duplicate leads to the master CSV and initializes their state 
    for the Resilient Cold Email Campaign Engine.
    
    CRITICAL: This function prevents duplicate sending by checking existing emails.
    """
    if not new_leads:
        print("Ingestion skipped: No new leads provided.")
        return

    # --- 1. Load the existing CSV file ---
    try:
        df_master = pd.read_csv(csv_file_path)
        print(f"Loaded existing master CSV (Rows: {df_master.shape[0]})")
    except FileNotFoundError:
        print(f"Master file not found at {csv_file_path}. Initializing new DataFrame.")
        df_master = pd.DataFrame()

    # Get a set of existing emails for fast, case-insensitive duplicate checking
    existing_emails = set(df_master['Email'].str.lower()) if 'Email' in df_master.columns else set()
    
    new_leads_to_add = []
    
    # --- 2. Process and Filter New Leads ---
    for lead in new_leads:
        # Normalize email for comparison
        email = lead.get('Email', '').strip().lower()
        
        # Critical duplicate check and validation
        if not email or email in existing_emails:
            if email:
                print(f"  [SKIPPED] Duplicate or invalid email found: {lead.get('Email')}")
            continue

        # --- 3. Initialize the Lead Row with Scraped Data and Default State ---
        new_row = {
            'Name': lead.get('Name'),
            'Title': lead.get('Title'),
            'Email': lead.get('Email'),
            'Company': lead.get('Company'),
            'Location': lead.get('Location', None),     
            'Source': lead.get('Source', 'LinkedIn_Scraper'), 
            'HiringScore': lead.get('HiringScore', 1), 
            
            # CRITICAL STATE MANAGEMENT INITIALIZATION
            'Sent_Status': 'PENDING',                  
            'Sent_Timestamp': None,                    
            'FollowUp_1_Status': 'PENDING',
            'FollowUp_2_Status': 'PENDING',
            'FollowUp_1_Timestamp': None,              
            'FollowUp_2_Timestamp': None               
        }
        new_leads_to_add.append(new_row)

    if not new_leads_to_add:
        print("Ingestion complete: All new leads were duplicates or invalid.")
        return

    # --- 4. Prepare for Concatenation ---
    df_new = pd.DataFrame(new_leads_to_add)
    
    # Ensure column alignment: Get final columns from the master file
    final_cols = df_master.columns.tolist() if not df_master.empty else df_new.columns.tolist()
    
    # Fill any missing columns in the new DataFrame with None
    for col in final_cols:
        if col not in df_new.columns:
            df_new[col] = None

    df_new = df_new[final_cols] # Order the columns correctly

    # --- 5. Append and Write Back to State File ---
    df_master = pd.concat([df_master, df_new], ignore_index=True)
    
    df_master.to_csv(csv_file_path, index=False)
    print(f"Successfully ingested {len(new_leads_to_add)} NEW unique leads into {csv_file_path}.")
    print("These leads are now marked 'PENDING' and ready for the campaign engine.")

if __name__ == '__main__':
    # Test block
    print("Running ingest_function.py in test mode...")
    test_leads = [{'Name': 'Test Lead', 'Title': 'Test Title', 'Email': 'test@example.com', 'Company': 'TestCorp'}]
    ingest_new_leads(test_leads)
    print("Test run complete.")