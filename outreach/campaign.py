import pandas as pd
import time
import random
from datetime import datetime
import logging
import os
import sys
from pathlib import Path
import dotenv # 1. Import dotenv

# =========================================================
# 🚨 CRITICAL FIX: LOAD .ENV IMMEDIATELY 
# This must run before 'from . import config' is attempted.
# =========================================================
ENV_PATH = Path(__file__).parent.parent / '.env'
print(f"--- DIAGNOSTICS ---")
print(f"Checking for .env at: {ENV_PATH}")
# This loads the environment variables (like SENDER_PASSWORD) from your .env file
dotenv_loaded = dotenv.load_dotenv(ENV_PATH) 
print(f"dotenv load status: {dotenv_loaded}")
print(f"--- END DIAGNOSTICS ---")
# =========================================================

# --- NEW FUNCTION FOR ATOMIC SAVE (Fault-Tolerance Fix) ---
def save_campaign_state(df_to_save, csv_path):
    """Performs a safe, atomic save of the campaign state to the CSV."""
    try:
        tmp_file = str(csv_path) + ".tmp"
        df_to_save.to_csv(tmp_file, index=False)
        os.replace(tmp_file, str(csv_path))
        logging.info("State saved successfully.")
        print(f"  ✅ State saved.")
        return True
    except Exception as e:
        logging.error(f"FATAL: CSV save failed: {e}")
        print(f"  ❌ FATAL ERROR: Failed to save CSV state: {e}")
        return False
# -----------------------------------------------------------

# Handling imports with fallback for running as script vs module
# This ensures the code runs correctly whether called directly or imported.
try:
    # 2. Imports of local modules happen AFTER .env is loaded
    from . import config
    from . import templates
    from .filters import filter_recipients_by_stage
    from .mailer import SMTPMailer
except ImportError:
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from outreach import config
    from outreach import templates
    from outreach.filters import filter_recipients_by_stage
    from outreach.mailer import SMTPMailer


def run_campaign():
    """Orchestrates the email outreach campaign."""

    # --- 1. Initial Setup and Load Data ---
    # This calls config.setup_logging(), which checks SENDER_PASSWORD (now loaded)
    if not config.setup_logging(): 
        return

    # Set up path to CSV file
    project_root = Path(__file__).parent.parent
    csv_path = project_root / config.FILE_TO_LOAD

    try:
        # Load the contact file
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"\nFATAL ERROR: Contact file '{csv_path}' not found.")
        logging.error(f"File not found: {csv_path}")
        return

    # Initialize tracking columns if missing
    tracking_cols = [
        'Sent_Status',
        'Sent_Timestamp',
        'FollowUp_1_Status',
        'FollowUp_1_Timestamp',
        'FollowUp_2_Status',
        'FollowUp_2_Timestamp',
    ]
    for col in tracking_cols:
        if col not in df.columns:
            df[col] = 'PENDING' if 'Status' in col else ''
            
    for ts_col in ['Sent_Timestamp', 'FollowUp_1_Timestamp', 'FollowUp_2_Timestamp']:
        df[ts_col] = df[ts_col].astype('string')


    # --- 1b. Daily Send Limit Check ---
    remaining_quota = config.DAILY_SEND_LIMIT
    
    if not config.TEST_MODE:
        today_str = pd.Timestamp.now().strftime('%Y-%m-%d')

        if config.CAMPAIGN_STAGE == 'INITIAL_SEND':
            ts_col = 'Sent_Timestamp'
            status_col = 'Sent_Status'
        elif config.CAMPAIGN_STAGE == 'FOLLOW_UP_1':
            ts_col = 'FollowUp_1_Timestamp'
            status_col = 'FollowUp_1_Status'
        else:
            ts_col = 'FollowUp_2_Timestamp'
            status_col = 'FollowUp_2_Status'

        sent_mask = df[status_col] == 'SENT_SUCCESS'
        sent_today_count = 0
        if sent_mask.any():
            ts_series = df.loc[sent_mask, ts_col].astype(str)
            sent_today_count = ts_series.str.startswith(today_str).sum()

        remaining_quota = max(0, config.DAILY_SEND_LIMIT - sent_today_count)

        print(f"\nQuota check: {sent_today_count} sent today. Remaining quota: {remaining_quota}")
        if remaining_quota == 0:
            print("Daily send limit reached for this stage. Exiting.")
            return

    
    # --- 2. Filter Recipients and Apply Limit ---
    recipients = filter_recipients_by_stage(df)

    if config.TEST_MODE:
        recipients = recipients.head(config.MAX_EMAILS_IN_TEST)
        print(f"\n--- RUNNING IN TEST MODE ({config.CAMPAIGN_STAGE}) (Sending {len(recipients)} Emails) ---")
    else:
        recipients = recipients.head(remaining_quota)
        print(f"\n--- RUNNING IN PRODUCTION MODE ({config.CAMPAIGN_STAGE}) (Sending max {len(recipients)} Emails) ---")

    if recipients.empty:
        print(f"No new {config.CAMPAIGN_STAGE} emails to send today. Exiting.")
        return

    # --- 3. Establish SMTP connection ---
    mailer = SMTPMailer()
    if not mailer.connect():
        return

    # --- 4. Send Loop and State Tracking ---
    df_to_update = df.copy()
    sent_count = 0

    status_col = (
        'Sent_Status' if config.CAMPAIGN_STAGE == 'INITIAL_SEND'
        else 'FollowUp_1_Status' if config.CAMPAIGN_STAGE == 'FOLLOW_UP_1'
        else 'FollowUp_2_Status'
    )
    timestamp_col = (
        'Sent_Timestamp' if config.CAMPAIGN_STAGE == 'INITIAL_SEND'
        else 'FollowUp_1_Timestamp' if config.CAMPAIGN_STAGE == 'FOLLOW_UP_1'
        else 'FollowUp_2_Timestamp'
    )


    for index, row in recipients.iterrows():
        first_name = templates.get_salutation_name(row['Name'])
        company = row['Company']
        title = row['Title']
        email = row['Email']
        score = row['HiringScore']

        if config.CAMPAIGN_STAGE == 'INITIAL_SEND':
            template = templates.get_initial_template(score, title)
            subject = template['subject'].format(Company=company)
        else:
            template = templates.TEMPLATE_MAP[config.CAMPAIGN_STAGE]
            subject = template['subject'] 

        body = template['body'].format(
            FirstName=first_name,
            Company=company
        )

        print(f"\nAttempting {config.CAMPAIGN_STAGE} to {first_name} at {company} ({email})...")

        send_result = mailer.send_email(email, subject, body)
        timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')

        if send_result == "SUCCESS":
            df_to_update.loc[index, status_col] = 'SENT_SUCCESS'
            df_to_update.loc[index, timestamp_col] = timestamp
            
            print(f"  [SUCCESS] Email sent: {subject}")
            sent_count += 1
            
            # --- CRITICAL FIX: SAVE STATE IMMEDIATELY AFTER SUCCESS ---
            save_campaign_state(df_to_update, csv_path)
            # --------------------------------------------------------
            
        elif send_result == 'FAILED_REFUSED':
            df_to_update.loc[index, status_col] = 'FAILED_REFUSED'
            print(f"  [FAILURE] Recipient refused (Bad Email).")

        else: # send_result is FAILED_OTHER
            df_to_update.loc[index, status_col] = 'FAILED_OTHER'
            print(f"  [FAILURE] Unknown error.")

        # --- Safety Delay (Variable) ---
        wait_time = random.randint(5, 15)
        print(f"  ...Waiting {wait_time} seconds (Safety Delay)...")
        time.sleep(wait_time)

    # --- 5. Final Cleanup ---
    
    # Disconnect safely
    mailer.disconnect()

    # Final save logic (a second safety net for FAILED statuses)
    try:
        tmp_file = str(csv_path) + ".tmp"
        df_to_update.to_csv(tmp_file, index=False)
        os.replace(tmp_file, str(csv_path))
        logging.info("Final CSV state saved successfully")
        print(f"✅ Final CSV file state saved: {csv_path}")
    except Exception as e:
        logging.error(f"Final CSV save failed: {e}")
        print(f"❌ ERROR: Failed to save final CSV state: {e}")
        
    print(f"\n--- Campaign Run Complete ({config.CAMPAIGN_STAGE}) ---")
    print(f"Total recipients processed: {len(recipients)}")
    print(f"Total emails successfully sent: {sent_count}")


if __name__ == "__main__":
    run_campaign()