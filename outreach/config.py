import os
import logging

# =========================================================
# CREDENTIALS & CONSTANTS
# =========================================================

# --- SENDER DETAILS (Update these for production) ---
# NOTE: Use an App Password if using Gmail.
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "your_email@gmail.com") 
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "YOUR_GENERATED_APP_PASSWORD") 

# SMTP SERVER (Standard for Gmail)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587 # Port for TLS

# CAMPAIGN SETTINGS
FILE_TO_LOAD = "cold_email_outreach_all_cleaned_ranked.csv"
LOG_FILE = "outreach_campaign.log"
DAILY_SEND_LIMIT = 450

# --- CAMPAIGN STAGE SWITCH (Change this for follow-ups) ---
# Options: 'INITIAL_SEND', 'FOLLOW_UP_1', 'FOLLOW_UP_2'
CAMPAIGN_STAGE = 'INITIAL_SEND' 

# RUN MODE
TEST_MODE = False # Set to False for a production run
MAX_EMAILS_IN_TEST = 5 # Number of emails to send in TEST_MODE

# =========================================================
# LOGGING SETUP
# =========================================================

def setup_logging():
    """Initializes the logging configuration."""
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    if SENDER_PASSWORD == "YOUR_GENERATED_APP_PASSWORD":
        print("\nFATAL ERROR: Please update SENDER_PASSWORD in config.py.")
        logging.error("Configuration error: SENDER_PASSWORD not updated.")
        return False
    return True