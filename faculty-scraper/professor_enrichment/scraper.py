# python -m faculty-scraper.professor_enrichment.run_enrichment

import requests
import re
import time
from bs4 import BeautifulSoup

from ..html_extractors.generic import extract_generic_text
from ..html_extractors.harvard import extract_harvard_text

from .config import HEADERS, REQUESTS_TIMEOUT, LOG_DETAIL, MODE
from .nlp_processor import (
    extract_primary_focus,
    confidence_score,
    build_personalization_line,
    calculate_hiring_score,
    infer_domain,
    infer_research_question,
    generate_subject_line,
)

# ============================================================
# HELPER FUNCTIONS (Removed generate_harvard_url_from_name)
# ============================================================

# ============================================================
# UNIVERSITY DETECTION
# ============================================================

def detect_university(url: str) -> str:
    url = (url or "").lower()
    if "harvard.edu" in url:
        return "harvard"
    if "ucla.edu" in url:
        return "ucla"
    if "berkeley.edu" in url:
        return "berkeley"
    if "illinois.edu" in url:
        return "uiuc"
    return "generic"


# ============================================================
# UCLA-SPECIFIC EXTRACTION
# ============================================================
# (No changes here)

def extract_ucla_research_text(soup):
    """
    UCLA faculty pages:
    Research often appears inside tables or under
    'Research and Teaching Interests'
    """
    article = soup.find("article", class_="entry-content")
    if not article:
        return ""

    # Direct hit via section title
    strong = article.find(
        "strong",
        string=lambda s: s and "research and teaching interests" in s.lower()
    )
    if strong:
        parent = strong.find_parent("p")
        if parent:
            next_p = parent.find_next_sibling("p")
            if next_p:
                return next_p.get_text(" ", strip=True)

    # Fallback: scan table cells
    candidates = []
    for td in article.find_all("td"):
        text = td.get_text(" ", strip=True)
        if (
            len(text) > 60
            and not any(bad in text.lower() for bad in [
                "award", "fellow", "member", "honor", "professor"
            ])
        ):
            candidates.append(text)

    return max(candidates, key=len) if candidates else ""


# ============================================================
# ERROR HANDLING
# ============================================================
# (No changes here)

def build_error_response(url, name, error_type, detail):
    if MODE == "TEST" and LOG_DETAIL >= 1:
        print(f"[ERROR] {name} → {error_type}")

    return {
        "Primary_Focus": "N/A",
        "Source_Sentence": "N/A",
        "Research_Question_Hint": "N/A",
        "Personalization_Line": build_personalization_line(None, 0, None),
        "Email_Subject": generate_subject_line(None, 0, None),
        "HiringScore": 5,
        "Confidence": 0,
        "Research_Areas": "ERROR",
        "Domain": "N/A",
        "Scrape_Status": f"FAILURE: {error_type}",
        "Error_Detail": detail.replace("\n", " ").strip(),
    }


# ============================================================
# MAIN SCRAPER
# ============================================================

def scrape_and_process_profile(row):
    url = row.get("PROFILE LINK")
    name = row.get("NAME", "Unknown")

    # The data preparation phase (in run_enrichment.py) now ensures 
    # 'PROFILE LINK' is populated for Harvard. 
    # We remove the FIX 2.2 Harvard auto-recovery logic here.

    if not url or not isinstance(url, str) or not url.startswith("http"):
        return build_error_response(url, name, "InvalidURL", "Invalid or missing URL (Data Prep Failed)")

    # Normalize http → https
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]

    # Berkeley fallback URLs (This remains as it is not a data prep issue)
    candidates = [url]
    if "eecs.berkeley.edu/Faculty/Homepages/" in url:
        slug = url.split("/")[-1].replace(".html", "")
        candidates += [
            f"https://www2.eecs.berkeley.edu/people/{slug}/",
            f"https://www2.eecs.berkeley.edu/faculty/{slug}/",
            f"https://people.eecs.berkeley.edu/~{slug}/",
        ]

    response = None
    final_url = None
    MAX_RETRIES = 3 

    # FIX 3.2: Implement retry/backoff loop (remains unchanged)
    for u in candidates:
        for attempt in range(MAX_RETRIES):
            try:
                r = requests.get(
                    u,
                    headers=HEADERS,
                    timeout=(3.0, REQUESTS_TIMEOUT),
                )
                if r.status_code == 200:
                    response = r
                    final_url = u
                    break
            except requests.exceptions.ConnectTimeout:
                # Exponential backoff: 1.5s, 3.0s, 4.5s
                time.sleep(1.5 * (attempt + 1))
            except requests.exceptions.RequestException:
                break
        
        if response:
            break


    if not response:
        return build_error_response(url, name, "ConnectTimeout", "All URL attempts failed")

    soup = BeautifulSoup(response.content, "html.parser")
    university = detect_university(final_url) 

    if MODE == "TEST" and LOG_DETAIL >= 2:
        print(f"[DEBUG] {name} → {university}")

    # ========================================================
    # UNIVERSITY-AWARE EXTRACTION
    # ========================================================

    if university == "harvard":
        source_text = extract_harvard_text(soup)

    elif university == "ucla":
        source_text = extract_ucla_research_text(soup)

    else:
        source_text = extract_generic_text(soup)

    # ========================================================
    # NLP + SCORING
    # ========================================================

    primary_focus = extract_primary_focus(source_text)
    # FIX 1: confidence_score call with the 'university' argument (remains unchanged)
    confidence = confidence_score(primary_focus, source_text, university) 
    research_question = infer_research_question(primary_focus)

    personalization_line = build_personalization_line(
        primary_focus, confidence, research_question
    )

    subject_line = generate_subject_line(
        primary_focus, confidence, research_question
    )

    hiring_score = calculate_hiring_score(primary_focus)
    domain = infer_domain(primary_focus)

    return {
        "Primary_Focus": primary_focus,
        "Source_Sentence": primary_focus,
        "Research_Question_Hint": research_question,
        "Personalization_Line": personalization_line,
        "Email_Subject": subject_line,
        "HiringScore": hiring_score,
        "Confidence": confidence,
        "Research_Areas": source_text,
        "Domain": domain,
        "Scrape_Status": "SUCCESS",
        "Error_Detail": "N/A",
    }