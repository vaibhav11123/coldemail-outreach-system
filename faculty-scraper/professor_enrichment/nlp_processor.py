# coldemail/faculty-scraper/professor_enrichment/nlp_processor.py

import re
from .config import AI_KEYWORDS

ROLE_PATTERNS = [
    r'\bprofessor\b',
    r'\bdirector\b',
    r'\bco-director\b',
    r'\bfellow\b',
    r'\baward\b',
    r'\bhas received\b',
    r'\bclass has been taken\b',
    r'\bfounded\b',
    r'\badvises\b'
]

RESEARCH_VERBS = [
    r'\bstudy\b',
    r'\binvestigate\b',
    r'\bexplore\b',
    r'\bdevelop\b',
    r'\bpropose\b',
    r'\banalyze\b',
    r'\bdesign\b',
    r'\bmodel\b',
    r'\blearn\b',
    r'\boptimiz',
    r'\btheor'
]

def is_role_sentence(sentence):
    """Returns True if the sentence is biographical/role-based rather than research-substantive."""
    s = sentence.lower()
    return any(re.search(p, s) for p in ROLE_PATTERNS)

def has_research_signal(sentence):
    s = sentence.lower()
    return any(re.search(v, s) for v in RESEARCH_VERBS)

# All NLP and scoring functions go here (from original Section 1)

def extract_sentences(text):
    """Splits a block of text into clean sentences, filtering out short ones."""
    if not text or not isinstance(text, str):
        return []
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 40]

def score_sentence(sentence):
    """Scores a sentence based on the presence of high-value AI/ML keywords."""
    s = sentence.lower()
    return sum(1 for kw in AI_KEYWORDS if kw in s)

def extract_primary_focus(text_content):
    """Takes a blob of text and extracts the single best, research-substantive sentence."""
    sentences = extract_sentences(text_content)
    if not sentences:
        return None

    # Remove biographical / role-based sentences and keep those with research signals
    sentences = [
        s for s in sentences
        if not is_role_sentence(s) and has_research_signal(s)
    ]
    if not sentences:
        return None

    ranked = sorted(
        sentences,
        key=lambda s: score_sentence(s),
        reverse=True
    )

    best_sentence = ranked[0]

    for fragment in ["my research focuses on", "we are working on", "i am interested in", "the goal is to"]:
        if best_sentence.lower().startswith(fragment):
            best_sentence = best_sentence[len(fragment):].strip()

    best_sentence = re.sub(r'^(professor|dr|mr|ms)\s+[A-Z][a-z]+.*?\b(is|are)\b', '', best_sentence, flags=re.I)
    return best_sentence.strip(' ,.')

# --- START OF REPLACED/CORRECTED FUNCTIONS (from Instruction 1) ---

def confidence_score(primary_focus, research_areas, university): # <-- FIX: Added 'university' parameter
    """
    Confidence scale (TIGHTENED LOGIC, now university-aware):
    0 = fallback / unsafe
    1 = weak but specific (length/keyword hit)
    2 = solid research signal (research verb/multi-keyword)
    3 = very strong, multi-signal (all three signals)
    """

    if not primary_focus:
        return 0

    score = 0
    focus = primary_focus.lower()
    is_harvard = (university == "harvard")

    # Signal 1: Length-based signal (Specificity/Detail)
    # Harvard's bios are often short but direct (SEAS uses short summaries)
    length_threshold = 40 if not is_harvard else 25 # Lower threshold for Harvard
    if len(primary_focus) > length_threshold:
        score += 1

    # Signal 2: Keyword density signal (Domain Relevance)
    keyword_hits = sum(1 for kw in AI_KEYWORDS if kw in focus)
    if keyword_hits >= 2:
        score += 1
    elif is_harvard and keyword_hits >= 1:
        # Give Harvard a slight bump for a single direct keyword hit
        score += 1

    # Signal 3: Research verb signal (Intent)
    if has_research_signal(primary_focus):
        score += 1
        
    # Final check for Harvard: If they have at least 1 keyword and a research verb, 
    # and passed the length check, they are solid (2). 
    # We want to prevent fake inflation, so keep the maximum at 3.
    
    return min(score, 3)

def build_personalization_line(primary_focus, confidence, research_question=None):
    """
    Confidence-aware, senior research tone (REPLACED/TIGHTENED).
    """

    if confidence == 0 or not primary_focus:
        return (
            "I’ve been following recent developments in the field and "
            "would value the opportunity to learn more about your research direction."
        )

    # Format the focus for insertion
    focus = primary_focus[0].lower() + primary_focus[1:]

    if confidence >= 3 and research_question:
        return (
            f"I’ve been reading your work on {focus}, "
            f"particularly how it connects to {research_question}."
        )

    if confidence == 2:
        return (
            f"I’ve been going through your work on {focus}, "
            "and would appreciate learning more about how you approach these problems."
        )

    return (
        f"I came across your work on {focus}, "
        "and would value the opportunity to understand the broader research context."
    )

def generate_subject_line(primary_focus, confidence, research_question=None):
    """
    Confidence-aware subject line generation (NEW ADDITION/REPLACEMENT).
    """

    if confidence == 0 or not primary_focus:
        return "Research discussion"

    # Get the first, main part of the focus, ignoring secondary clauses
    short_focus = re.split(r',|;| and ', primary_focus)[0]

    if confidence >= 3 and research_question:
        return f"On {research_question}"

    if confidence == 2:
        return f"Thoughts on {short_focus}"

    return f"Regarding your work on {short_focus}"

# --- END OF REPLACED/CORRECTED FUNCTIONS ---


def infer_domain(text):
    """Adds a Research Domain Tag for easier targeting and subject line generation."""
    t = (text or "").lower()
    # (Domain inference logic remains the same)
    if "reinforcement" in t or "robot" in t or "autonom" in t:
        return "Robotics / RL"
    # ... (other domain checks) ...
    if "vision" in t or "image" in t:
        return "Computer Vision"
    if "nlp" in t or "language" in t or "transformer" in t:
        return "NLP / Language"
    if "foundation" in t or "representation" in t or "causal" in t:
        return "Foundations / Theory"
    if "data science" in t or "optimization" in t:
        return "Data Science / Optimization"
        
    return "General ML"

def calculate_hiring_score(primary_focus):
    """Calculates a deterministic score based on research topics."""
    score = 10 
    # (Hiring score logic remains the same)
    if not primary_focus:
        return score
    # ... (scoring logic) ...
    focus = primary_focus.lower()
    if any(k in focus for k in ["reinforcement", "foundation", "robotics", "representation", "causal"]):
        score += 40
    if any(k in focus for k in ["deep learning", "optimization", "neural", "computer vision", "generative ai"]):
        score += 30
    if any(k in focus for k in ["machine learning", "nlp", "artificial intelligence", "data science"]):
        score += 15
    if "lab" in focus or "center" in focus:
        score += 10
        
    return min(score, 95) 

def infer_research_question(primary_focus):
    """
    Converts a research statement into an implicit research question.
    This is used to sound like a peer, not a fanboy.
    """
    if not primary_focus:
        return None

    t = primary_focus.lower()

    # Pattern-based question inference
    if any(k in t for k in ["reinforcement", "policy", "control"]):
        return "how learning-based control policies can generalize reliably"
    if any(k in t for k in ["representation", "foundation", "unsupervised"]):
        return "how robust representations emerge from data"
    if any(k in t for k in ["vision", "image", "perception"]):
        return "how perceptual structure can be learned efficiently"
    if any(k in t for k in ["language", "nlp", "transformer"]):
        return "how language models capture semantic structure"
    if any(k in t for k in ["optimization", "theory"]):
        return "how optimization dynamics shape learning behavior"

    # Generic fallback
    return "how learning systems can be made more robust and general"