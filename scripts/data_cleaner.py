import pandas as pd
import pdfplumber
import re

CSV_FILE = "../data/raw/14400+ Ultimate HR Outreach List  - DataNiti - 2500+ HR's Manager Contacts with Profiles - .csv"
PDF_FILE = "../data/raw/Company Wise HR Contacts - HR Contacts.pdf"

# ===============================
# TEST MODE CONFIG
# ===============================
TEST_MODE = False         # ← set False for full run
TEST_CSV_ROWS = 30        # rows from CSV
TEST_PDF_PAGES = 2        # pages from PDF

OUTPUT_FILE = (
    "../data/processed/cold_email_TEST_sample.csv"
    if TEST_MODE
    else "../data/processed/cold_email_outreach_all_cleaned_ranked.csv"
)

# =========================================================
# CLEANING HELPERS
# =========================================================

def clean_email(email):
    if not email:
        return None
    email = str(email).strip().lower()
    return re.sub(r"[^\w@\.\-\+]", "", email)

def clean_text(val):
    if not val:
        return "N/A"
    return re.sub(r"\s+", " ", str(val)).strip()

def clean_name(name):
    return clean_text(name).title()

def clean_title(title):
    return clean_text(title)

def clean_company(company):
    return clean_text(company).title()

# =========================================================
# PDF PARSER (EMAIL-ANCHORED)
# =========================================================

def parse_hr_pdf(pdf_path):
    rows = []

    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages[:TEST_PDF_PAGES] if TEST_MODE else pdf.pages

        for page in pages:
            tables = page.extract_tables()
            if not tables:
                continue

            for table in tables:
                # Skip empty or malformed tables
                if len(table) < 2:
                    continue

                header = table[0]

                for row in table[1:]:
                    if not row:
                        continue

                    # Remove None cells
                    cells = [c for c in row if c and str(c).strip()]

                    # We need at least: Name, Email/Title, Company
                    if len(cells) < 3:
                        continue

                    # Heuristic mapping:
                    # First non-empty cell after SNo → Name
                    # Last cell → Company
                    # Middle cells → Title + Email blob
                    name_raw = cells[1] if len(cells) > 1 else cells[0]
                    company_raw = cells[-1]
                    middle_raw = "\n".join(cells[2:-1]) if len(cells) > 3 else cells[2]

                    email = None
                    title = None

                    parts = [p.strip() for p in middle_raw.split("\n") if p.strip()]
                    for p in parts:
                        if re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', p):
                            email = clean_email(p)
                        elif title is None:
                            title = p

                    if not email:
                        continue

                    rows.append([
                        clean_name(name_raw),
                        clean_title(title),
                        email,
                        clean_company(company_raw),
                        "PDF_Source",
                        "N/A"
                    ])

    return pd.DataFrame(
        rows,
        columns=["Name", "Title", "Email", "Company", "Source", "Location"]
    )

# =========================================================
# CSV CLEANER
# =========================================================

def process_csv(csv_path):
    df = pd.read_csv(csv_path, skiprows=3, encoding="latin-1")

    if TEST_MODE:
        df = df.head(TEST_CSV_ROWS)

    df.rename(columns={"Company Name": "Company"}, inplace=True)

    df["Name"] = "N/A"
    df["Title"] = "HR Contact"
    df["Source"] = "CSV_Source"

    df = df[["Name", "Title", "Email", "Company", "Location", "Source"]]

    df["Email"] = df["Email"].apply(clean_email)
    df["Company"] = df["Company"].apply(clean_company)
    df["Title"] = df["Title"].apply(clean_title)

    df = df[
        df["Email"].notna() &
        df["Email"].str.contains("@", na=False) &
        ~df["Email"].str.contains(
            r"(https?://|forms\.gle|careers@|jobs@)",
            case=False,
            na=False
        )
    ]

    return df

# =========================================================
# HIRING SCORE
# =========================================================

def hiring_score(title):
    t = title.lower()

    if re.search(r'\b(founder|co-founder|ceo|cto|cfo|coo)\b', t):
        return 100
    if re.search(r'\b(chief people officer|chro)\b', t):
        return 90
    if re.search(r'\b(vp|vice president|svp|evp)\b', t):
        return 80
    if re.search(r'\b(director|global head)\b', t):
        return 70
    if re.search(r'\b(head of talent|head of recruitment|head hr)\b', t):
        return 60
    if re.search(r'\b(talent acquisition|recruitment)\b', t):
        return 50
    if re.search(r'\b(hr|human resources)\b', t):
        return 30
    return 10

# =========================================================
# MAIN
# =========================================================

def main():
    csv_df = process_csv(CSV_FILE)
    pdf_df = parse_hr_pdf(PDF_FILE)

    df = pd.concat([csv_df, pdf_df], ignore_index=True)

    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    df = df[df["Email"].str.match(email_pattern, na=False)]

    df["HiringScore"] = df["Title"].apply(hiring_score)
    df = df.sort_values(by="HiringScore", ascending=False)
    df = df.drop_duplicates(subset=["Email", "Company"], keep="first")

    df[
        ["Name", "Title", "Email", "Company", "Location", "Source", "HiringScore"]
    ].to_csv(OUTPUT_FILE, index=False)

    print(f"\n✅ Saved {len(df)} records → {OUTPUT_FILE}")
    print("\n🔍 Preview:")
    print(df.head(10))

if __name__ == "__main__":
    main()