import os
import time
import re
import random 
from typing import List, Dict, Any
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager 
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv 
import sys # <-- Added for safe program exit

# Load environment variables from .env file (must be in the project root)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


# Ensure linkedin_scraper is installed
try:
    from linkedin_scraper import actions, Person 
except ImportError:
    print("Error: The 'linkedin_scraper' library is required. Please install it.")
    sys.exit(1)

# Import the crucial ingestion logic from the sibling file
from ingest_function import ingest_new_leads 

# --- 1. CLEANING AND SCORING LOGIC HELPERS (UNCHANGED) ---

TECH_TITLE_KEYWORDS = re.compile(r'\b(cto|chief technology officer|head of ai|engineering|tech head|data science director)\b', re.I)

def clean_lead_data(value: str, key: str) -> str:
    # ... (code for clean_lead_data) ...
    if not value: return ""
    value = str(value)
    value = re.sub(r'\([^)]*\)', '', value)
    value = re.sub(r'[^\w\s\-,.&/]', '', value)
    value = ' '.join(value.split()).strip()
    if key == 'Name':
        value = re.sub(r'\b(mr|ms|mrs|dr|phd|m.d.|p.e.|sr|jr|iii)\.?\b', '', value, flags=re.IGNORECASE)
        value = value.title()
    elif key == 'Email':
        value = value.lower()
        if not re.match(r"[^@]+@[^@]+\.[^@]+", value): return None
    elif key in ['Title', 'Company']:
        value = value.title()
    return value.strip()


def calculate_hiring_score(title: str) -> int:
    # ... (code for calculate_hiring_score) ...
    title_lower = str(title).lower()
    if re.search(TECH_TITLE_KEYWORDS, title_lower): return 95 
    if any(keyword in title_lower for keyword in ['director', 'vp', 'recruiter', 'hrbp', 'talent acquisition', 'head of']): return 70
    return 10


# --- 2. CONFIGURATION & MODE SWITCH (READ FROM .ENV) ---

# Read credentials and limits
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")
MAX_PROFILES_TO_SCRAPE = int(os.getenv("MAX_PROFILES_TO_SCRAPE", 30)) # Default to 30
SCRAPER_MODE = os.getenv("SCRAPER_MODE", "TEST").upper() # Default to TEST

# Read delays
LOGIN_DELAY_MIN = float(os.getenv("LOGIN_DELAY_MIN", 5))
LOGIN_DELAY_MAX = float(os.getenv("LOGIN_DELAY_MAX", 8))
SCROLL_DELAY_MIN = float(os.getenv("SCROLL_DELAY_MIN", 1.5))
SCROLL_DELAY_MAX = float(os.getenv("SCROLL_DELAY_MAX", 3.5))
PROFILE_DELAY_MIN = float(os.getenv("PROFILE_DELAY_MIN", 3))
PROFILE_DELAY_MAX = float(os.getenv("PROFILE_DELAY_MAX", 7))


# --- 3. HARD SAFETY GUARDS ---
MAX_RUNTIME_SECONDS = 20 * 60  # 20 minutes max runtime
START_TIME = time.time()
LINKEDIN_BASE_SEARCH_URL = "https://www.linkedin.com/search/results/"

def runtime_exceeded():
    return (time.time() - START_TIME) > MAX_RUNTIME_SECONDS

# Mode enforcement and override
if SCRAPER_MODE not in {"TEST", "PROD"}:
    raise ValueError(f"SCRAPER_MODE must be TEST or PROD, got {SCRAPER_MODE}")

if SCRAPER_MODE == "TEST":
    # Hard-cap max profiles for safety during testing
    MAX_PROFILES_TO_SCRAPE = min(5, MAX_PROFILES_TO_SCRAPE)
    print("=========================================")
    print("🧪 RUNNING IN TEST MODE (max 5 profiles)")
    print("=========================================")
else:
    print("=========================================")
    print(f"🚀 RUNNING IN PRODUCTION MODE (max {MAX_PROFILES_TO_SCRAPE} profiles)")
    print("=========================================")


# --- 4. QUERY SETUP (Plug-and-Play) ---
QUERY_KEYS = sorted([k for k in os.environ if k.startswith("QUERY_")])
SEARCH_QUERIES = [os.getenv(k) for k in QUERY_KEYS if os.getenv(k)]

if not SEARCH_QUERIES:
    raise RuntimeError("No QUERY_* entries found in .env. Please define them.")


def run_lead_generation():
    """
    Orchestrates the scraping, cleaning, scoring, and ingestion process.
    """
    if not LINKEDIN_EMAIL or not LINKEDIN_PASSWORD:
        print("[FATAL] LinkedIn credentials not found. Please check your .env file.")
        return

    driver = None
    scraped_data = []
    total_scraped_count = 0

    try:
        # --- A. INITIALIZE BROWSER AND LOGIN ---
        print("1. Initializing Chrome Driver...")
        from selenium.webdriver.chrome.options import Options

        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)
        
        print("2. Attempting LinkedIn login...")
        actions.login(driver, LINKEDIN_EMAIL, LINKEDIN_PASSWORD)
        
        login_delay = random.uniform(LOGIN_DELAY_MIN, LOGIN_DELAY_MAX)
        print(f"   Login successful. Waiting for {login_delay:.2f} seconds...")
        time.sleep(login_delay) 


        # --- B. EXECUTE SCRAPE LOGIC: Loop through all configured queries ---
        
        for query_index, query in enumerate(SEARCH_QUERIES):
            if total_scraped_count >= MAX_PROFILES_TO_SCRAPE:
                print("Total profile limit reached across all queries. Stopping search.")
                break

            print(f"\n🔍 Query {query_index + 1}/{len(SEARCH_QUERIES)}: Searching for '{query}'")
            target_url = LINKEDIN_BASE_SEARCH_URL + query
            driver.get(target_url)
            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".reusable-search__result-container"))
            )
            
            profile_urls_to_scrape = []
            
            # Simple scrolling to load results 
            for _ in range(5): 
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                scroll_delay = random.uniform(SCROLL_DELAY_MIN, SCROLL_DELAY_MAX)
                time.sleep(scroll_delay) 
            
            # Extract profile URLs
            search_results = driver.find_elements(By.CSS_SELECTOR, ".reusable-search__result-container a.app-aware-link")
            
            for result in search_results:
                href = result.get_attribute('href')
                if "/in/" in href and href.endswith('/'):
                    clean_url = href.split('?')[0]
                    if clean_url not in profile_urls_to_scrape:
                        profile_urls_to_scrape.append(clean_url)
            
            print(f"   Found {len(profile_urls_to_scrape)} potential URLs for this query.")


            # --- C. SCRAPE DETAILS, CLEAN, SCORE, AND FORMAT ---
            
            for i, url in enumerate(profile_urls_to_scrape):
                if total_scraped_count >= MAX_PROFILES_TO_SCRAPE:
                    print(f"Total profile limit of {MAX_PROFILES_TO_SCRAPE} reached.")
                    break
                if runtime_exceeded():
                    print("⏱ Max runtime reached, stopping scrape safely.")
                    break
                
                # A. Hard Safety Guard: Check for ban/checkpoint
                if "checkpoint" in driver.current_url.lower():
                    raise ConnectionError("LinkedIn checkpoint triggered — stopping immediately")

                try:
                    print(f"   Scraping lead {total_scraped_count + 1}/{MAX_PROFILES_TO_SCRAPE}...")
                    person = Person(url, driver=driver, scrape=True)
                    
                    # Apply Cleaning
                    cleaned_name = clean_lead_data(person.name, 'Name')
                    cleaned_title = clean_lead_data(person.job_title, 'Title')
                    cleaned_email = clean_lead_data(person.email, 'Email')
                    cleaned_company = clean_lead_data(person.company, 'Company')
                    
                    # Apply Scoring
                    calculated_score = calculate_hiring_score(cleaned_title)

                    if cleaned_email and cleaned_name:
                        lead_data = {
                            'Name': cleaned_name,
                            'Title': cleaned_title,           
                            'Email': cleaned_email,
                            'Company': cleaned_company,           
                            'Location': None,                    
                            'Source': 'LinkedIn_Scraper',
                            'HiringScore': calculated_score,
                        }
                        scraped_data.append(lead_data)
                        total_scraped_count += 1
                        print(f"      [OK] Scored {calculated_score}. Appended: {cleaned_name}")
                    else:
                        print("      [SKIPPED] Missing required data or invalid format.")
                        
                    profile_delay = random.uniform(PROFILE_DELAY_MIN, PROFILE_DELAY_MAX)
                    time.sleep(profile_delay) # <-- Randomized delay
                    

                except Exception as e_scrape:
                    print(f"   [Error] Could not scrape {url}: {e_scrape}")
            
            if total_scraped_count >= MAX_PROFILES_TO_SCRAPE or runtime_exceeded():
                break


    except ConnectionError as e:
        print(f"\n[CRITICAL CONNECTION ERROR] {e}")
        scraped_data = []
        
    except Exception as e:
        print(f"\n[CRITICAL UNEXPECTED ERROR] Failed during Lead Generation Pipeline: {e}")
        scraped_data = [] 
        
    finally:
        if driver:
            driver.quit() # Always close the browser, regardless of success/fail
        
    # --- D. INGEST THE LEADS (The Bridge) ---
    print(f"\n4. Starting Ingestion of {len(scraped_data)} valid, cleaned leads...")
    ingest_new_leads(scraped_data)
    
    print("\n--- Lead Generation Pipeline Complete ---")
    print("Next step: Run your core campaign engine: python outreach/campaign.py")

if __name__ == "__main__":
    run_lead_generation()