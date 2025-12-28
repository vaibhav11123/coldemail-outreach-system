# coldemail/faculty-scraper/professor_enrichment/config.py

import os

# --- MODE CONTROL ---
# Set to 'PROD' for live, quiet runs. Set to 'TEST' for verbose debugging.
MODE = 'PROD'  
# LOG_DETAIL: 0 (Minimal, PROD default), 1 (Medium detail), 2 (Full traceback, TEST default)
LOG_DETAIL = 1 if MODE == 'TEST' else 0 

# --- TESTING LIMIT ---
# **This limits the number of rows processed when MODE is set to 'TEST'**
TEST_ROW_LIMIT = 5
# --- PERIODIC SAVE ---
# Save CSV after every N rows processed
SAVE_EVERY_N_ROWS = 5

# --- DATA DIRECTORY ---
# Path to the data directory containing university CSV files
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data'
)
# Note: os.path logic makes this path robust regardless of where you run the script from

# --- RATE LIMITING ---
BASE_SLEEP_TIME = 1.5      
REQUESTS_TIMEOUT = 10 

# --- NLP & SCORING ---
AI_KEYWORDS = [
    "machine learning", "deep learning", "reinforcement learning",
    "robotics", "computer vision", "nlp", "natural language processing",
    "artificial intelligence", "representation learning",
    "foundation models", "optimization", "neural networks", 
    "causal inference", "large language model", "data science", "generative ai" 
]

# --- NLP FILTERING (CRITICAL FOR RESEARCH TONE) ---
# Sentences containing these patterns are NOT considered research signals
BAD_SENTENCE_PATTERNS = [
    "professor", "director", "co-director", "chair",
    "has received", "has founded", "award", "honor",
    "featured in", "press", "media",
    "lab", "laboratory", "center", "institute",
    "fellow", "member of", "editor", "board",
]

# Verbs that indicate actual research activity (must appear in good sentences)
RESEARCH_VERBS = [
    "study", "investigate", "analyze", "develop",
    "propose", "explore", "model", "optimize",
    "learn", "learning", "reason", "infer",
    "design", "build", "formalize", "evaluate",
]

# --- URL RECOVERY RULES ---
# Used to recover from broken university faculty profile links
URL_RECOVERY_TEMPLATES = [
    "https://people.eecs.berkeley.edu/~{last}/",
    "https://people.eecs.berkeley.edu/~{first}/",
    "https://{last}.berkeley.edu/",
]

# --- PERSONALIZATION TONE PRESETS ---
# Used by NLP layer to avoid sounding like a beginner
PERSONALIZATION_TONE = {
    "high_confidence": (
        "I’ve been reading your work on {focus}, "
        "and was particularly interested in how it frames the underlying research trade-offs."
    ),
    "medium_confidence": (
        "I’ve been going through your recent work on {focus}, "
        "and would appreciate learning more about how you approach these problems."
    ),
    "low_confidence": (
        "I have been following recent work in learning-based systems "
        "and would value the opportunity to learn more about your research direction."
    ),
}

# --- SCRAPING HEADERS ---
# Improved User-Agent for bypassing simple bot checks
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}