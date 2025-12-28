import re

# Helper for Tech Titles in Template #3 logic
TECH_TITLE_KEYWORDS = re.compile(
    r'\b(cto|chief technology officer|head of ai|engineering|tech head|data science director)\b',
    re.I
)

# --- Template 1: Primary Cold Email (High-Score Leads: 90–100) ---
TEMPLATE_1 = {
    "id": "T1_PRIMARY",
    "subject": "Quick question re interns at {Company}",
    "body": """
Hi {FirstName},

Came across your profile while researching senior people leaders at {Company}.

I’m a B.Tech student at IIT Delhi, currently working on applied ML and data systems through internships and projects. I wanted to check if teams at {Company} ever work with interns or early-career engineers on data, ML, or analytics problems.

If this isn’t the right channel, happy to be routed to the right person.

Thanks,
Vaibhav Singh
IIT Delhi
LinkedIn: https://www.linkedin.com/in/vaibhav-singh-vs23/
"""
}

# --- Template 2: Ultra-Short Version (Score < 90) ---
TEMPLATE_2 = {
    "id": "T2_SHORT",
    "subject": "Quick check",
    "body": """
Hi {FirstName},

I’m a B.Tech student at IIT Delhi working on ML and data systems.
Quick check — do teams at {Company} engage interns or early-career engineers?

If not the right person, happy to be redirected.

Best,
Vaibhav
IIT Delhi
LinkedIn: https://www.linkedin.com/in/vaibhav-singh-vs23/
"""
}

# --- Template 3: ML-Focused Version (Tech-leaning leaders) ---
TEMPLATE_3 = {
    "id": "T3_ML_FOCUSED",
    "subject": "ML intern question",
    "body": """
Hi {FirstName},

I’m a B.Tech student at IIT Delhi working on applied ML and data systems through internships and projects.

Wanted to check if teams at {Company} ever bring on interns to work on real ML or data problems. Open to short, hands-on engagements as well.

If this isn’t the right place to ask, happy to be pointed to the right person.

Thanks,
Vaibhav
IIT Delhi
LinkedIn: https://www.linkedin.com/in/vaibhav-singh-vs23/
"""
}

# --- Template 4: First Follow-Up (6–7 days) ---
TEMPLATE_4 = {
    "id": "T4_FOLLOWUP_1",
    "subject": "Re: quick question",
    "body": """
Hi {FirstName},

Just following up in case this got buried.

No worries if this isn’t relevant — figured I’d check once.

Best,
Vaibhav
IIT Delhi
LinkedIn: https://www.linkedin.com/in/vaibhav-singh-vs23/
"""
}

# --- Template 5: Second Follow-Up (12–14 days, final) ---
TEMPLATE_5 = {
    "id": "T5_FOLLOWUP_2",
    "subject": "Re: quick question",
    "body": """
Hi {FirstName},

Closing the loop on this.
Thanks for your time either way.

Best,
Vaibhav
IIT Delhi
LinkedIn: https://www.linkedin.com/in/vaibhav-singh-vs23/
"""
}

# --- Template Map ---
TEMPLATE_MAP = {
    'INITIAL_SEND': {
        'T1': TEMPLATE_1,  # Score >= 90
        'T2': TEMPLATE_2,  # Score < 90
        'T3': TEMPLATE_3   # Tech titles
    },
    'FOLLOW_UP_1': TEMPLATE_4,
    'FOLLOW_UP_2': TEMPLATE_5
}

def get_salutation_name(name):
    """Extract first name safely or fall back."""
    name = str(name).strip()
    if name and name.lower() not in ('n/a', 'nan'):
        return name.split()[0]
    return 'Hiring Team'

def get_initial_template(score, title):
    """Selects template based on title and HiringScore."""
    title_lower = str(title).lower()

    # Rule 1: Tech titles
    if re.search(TECH_TITLE_KEYWORDS, title_lower):
        return TEMPLATE_MAP['INITIAL_SEND']['T3']

    # Rule 2: High-score leads
    if score >= 90:
        return TEMPLATE_MAP['INITIAL_SEND']['T1']

    # Rule 3: Default short template
    return TEMPLATE_MAP['INITIAL_SEND']['T2']