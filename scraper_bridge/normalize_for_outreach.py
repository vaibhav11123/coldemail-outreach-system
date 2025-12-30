"""
OUTREACH NORMALIZATION LAYER

This module transforms raw StaffSpy scraping output into outreach-ready data.
It enforces strict data contracts and business logic that scrapers don't provide.

Key principle: Scraping ≠ Outreach. Normalization is the business logic.
"""

import pandas as pd
import re
import ast
import logging
from typing import Dict, List, Tuple, Optional


# ============================================================
# STEP 1: STRICT OUTREACH SCHEMA (NON-NEGOTIABLE)
# ============================================================

OUTREACH_SCHEMA = [
    "company",
    "first_name",
    "last_name",
    "role",              # Canonical role (normalized)
    "seniority",         # IC, Manager, Director, VP, C-Level
    "department",        # Engineering, Product, etc.
    "linkedin_url",
    "company_domain",
    "email",
    "email_confidence",  # 0.0-1.0
    "source",
    "rejection_reason"   # Only in rejected_debug.csv
]


# ============================================================
# STEP 2: ROLE FILTERING (EXPLICIT ALLOW/DENY LISTS)
# ============================================================

# ALLOWED: Decision-adjacent roles only
ALLOWED_KEYWORDS = [
    # Leadership
    "director",
    "head",
    "vp",
    "vice president",
    "principal",
    "staff engineer",
    "engineering manager",
    "em",
    "tech lead",
    "lead engineer",
    "founder",
    "co-founder",
    "ceo",
    "cto",
    "cpo",
    "chief",
    # Senior IC
    "senior engineer",
    "senior software engineer",
    "staff",
    "principal engineer",
    # Product/Strategy
    "product manager",
    "head of product",
    "vp product",
    "director of product"
]

# EXPLICITLY EXCLUDED: Non-decision roles
EXCLUDED_KEYWORDS = [
    "intern",
    "internship",
    "sde-1",
    "sde-2",
    "sde 1",
    "sde 2",
    "qa",
    "test",
    "testing",
    "support",
    "student",
    "operations",
    "facilities",
    "supply chain",
    "hr",
    "talent",
    "recruiter",
    "recruiting",
    "delivery",
    "logistics",
    "facility",
    "admin",
    "administrative",
    "associate",  # Too junior unless explicitly "associate director"
    "junior",
    "entry level"
]


# ============================================================
# STEP 3: TITLE NORMALIZATION MAPPING
# ============================================================

ROLE_NORMALIZATION = {
    # Engineering Leadership
    r"engineering manager|em|eng manager": "Engineering Manager",
    r"director.*engineering|engineering director": "Director of Engineering",
    r"vp.*engineering|vice president.*engineering": "VP Engineering",
    r"head.*engineering|engineering head": "Head of Engineering",
    r"tech lead|technical lead|lead engineer": "Tech Lead",
    r"staff engineer|staff.*engineer": "Staff Engineer",
    r"principal engineer|principal.*engineer": "Principal Engineer",
    
    # Product
    r"product manager|pm": "Product Manager",
    r"director.*product|product director": "Director of Product",
    r"vp.*product|vice president.*product": "VP Product",
    r"head.*product|product head": "Head of Product",
    
    # C-Level
    r"chief.*technology|cto": "CTO",
    r"chief.*product|cpo": "CPO",
    r"chief.*executive|ceo": "CEO",
    r"founder|co-founder": "Founder",
    
    # Generic senior roles
    r"senior.*engineer|senior software engineer": "Senior Engineer",
    r"lead.*engineer": "Lead Engineer",

    # NEW: Catch-all for clear IC roles that pass the filter
    r"software developer|software engineer|sde|developer|engineer": "Software Engineer (IC)",
}


SENIORITY_MAPPING = {
    "Engineering Manager": "Manager",
    "Director of Engineering": "Director",
    "VP Engineering": "VP",
    "Head of Engineering": "Director",
    "Tech Lead": "Lead",
    "Staff Engineer": "Senior IC",
    "Principal Engineer": "Senior IC",
    "Product Manager": "Manager",
    "Director of Product": "Director",
    "VP Product": "VP",
    "Head of Product": "Director",
    "CTO": "C-Level",
    "CPO": "C-Level",
    "CEO": "C-Level",
    "Founder": "C-Level",
    "Senior Engineer": "Senior IC",
    "Lead Engineer": "Lead",
    "Software Engineer (IC)": "IC", # NEW
}


DEPARTMENT_MAPPING = {
    "Engineering Manager": "Engineering",
    "Director of Engineering": "Engineering",
    "VP Engineering": "Engineering",
    "Head of Engineering": "Engineering",
    "Tech Lead": "Engineering",
    "Staff Engineer": "Engineering",
    "Principal Engineer": "Engineering",
    "Product Manager": "Product",
    "Director of Product": "Product",
    "VP Product": "Product",
    "Head of Product": "Product",
    "CTO": "Engineering",
    "CPO": "Product",
    "CEO": "Executive",
    "Founder": "Executive",
    "Senior Engineer": "Engineering",
    "Lead Engineer": "Engineering",
    "Software Engineer (IC)": "Engineering", # NEW
}


# ============================================================
# STEP 4: HARD FILTERING FUNCTIONS
# ============================================================

def hard_filter_invalid_profiles(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Hard filter: Remove structurally unrecoverable rows.
    
    Returns:
        (valid_df, rejected_df) - rejected_df includes rejection_reason
    """
    initial_count = len(df)
    rejected_rows = []
    
    # Build rejection reasons
    rejection_reasons = []
    
    # Condition 1: LinkedIn Member (hidden profile)
    mask_linkedin_member = (
        df["name"].astype(str).str.contains("LinkedIn Member", case=False, na=False)
    )
    
    # Condition 2: Headless profile_id
    mask_headless = (
        df["profile_id"].isna()
        | (df["profile_id"].astype(str).str.contains("headless", case=False, na=False))
    )
    
    # Condition 3: Search results URL (not a real profile)
    mask_search_results = (
        df["profile_link"].astype(str).str.contains("/search/results/", case=False, na=False)
    )
    
    # Condition 4: Empty headline (no role information)
    mask_empty_headline = (
        df["headline"].isna()
        | (df["headline"].astype(str).str.strip() == "")
    )
    
    # Combine all invalid conditions
    invalid_mask = mask_linkedin_member | mask_headless | mask_search_results | mask_empty_headline
    
    # Create rejection reasons
    for idx in df[invalid_mask].index:
        reasons = []
        if mask_linkedin_member.loc[idx]:
            reasons.append("LinkedIn Member (hidden profile)")
        if mask_headless.loc[idx]:
            reasons.append("Headless profile_id")
        if mask_search_results.loc[idx]:
            reasons.append("Search results URL (not real profile)")
        if mask_empty_headline.loc[idx]:
            reasons.append("Empty headline")
        rejection_reasons.append("; ".join(reasons))
    
    # Split into valid and rejected
    rejected_df = df[invalid_mask].copy()
    valid_df = df[~invalid_mask].copy()
    
    if len(rejected_df) > 0:
        rejected_df["rejection_reason"] = rejection_reasons
    
    removed = initial_count - len(valid_df)
    
    if removed > 0:
        logging.info(f"HARD FILTER: Removed {removed} invalid profiles ({initial_count} → {len(valid_df)})")
    
    return valid_df, rejected_df


def filter_by_role_relevance(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Filter by explicit role allow/deny lists.
    
    Returns:
        (allowed_df, rejected_df)
    """
    initial_count = len(df)
    rejected_rows = []
    rejection_reasons = []
    
    # Get title text from multiple possible columns
    title_texts = []
    for idx, row in df.iterrows():
        title = (
            str(row.get("headline", "")).lower()
            + " " + str(row.get("position", "")).lower()
            + " " + str(row.get("current_position", "")).lower()
        )
        title_texts.append(title)
    
    df["_title_combined"] = title_texts
    
    # Check against allow/deny lists
    allowed_mask = pd.Series([False] * len(df), index=df.index)
    rejection_mask = pd.Series([False] * len(df), index=df.index)
    
    for idx, row in df.iterrows():
        title_lower = row["_title_combined"]
        
        # First check: explicit exclusions (hard reject)
        if any(excluded in title_lower for excluded in EXCLUDED_KEYWORDS):
            # Special case: "associate director" is allowed
            if "associate director" in title_lower:
                allowed_mask.loc[idx] = True
            else:
                rejection_mask.loc[idx] = True
                rejected_rows.append(idx)
                rejection_reasons.append("Excluded role keyword")
        # Second check: allowed keywords
        elif any(allowed in title_lower for allowed in ALLOWED_KEYWORDS):
            allowed_mask.loc[idx] = True
        else:
            # Neither explicitly allowed nor excluded - reject as unclear
            rejection_mask.loc[idx] = True
            rejected_rows.append(idx)
            rejection_reasons.append("Role not in allowlist or denylist")
    
    # Split into allowed and rejected
    allowed_df = df[allowed_mask].copy()
    rejected_df = df[rejection_mask].copy()
    
    if len(rejected_df) > 0:
        rejected_df["rejection_reason"] = rejection_reasons
    
    # Clean up temporary column
    allowed_df = allowed_df.drop(columns=["_title_combined"], errors="ignore")
    rejected_df = rejected_df.drop(columns=["_title_combined"], errors="ignore")
    
    removed = initial_count - len(allowed_df)
    if removed > 0:
        logging.info(f"ROLE FILTER: Removed {removed} non-relevant roles ({initial_count} → {len(allowed_df)})")
    
    return allowed_df, rejected_df


# ============================================================
# STEP 5: TITLE NORMALIZATION
# ============================================================

def normalize_role(headline: str, position: str = "") -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Normalize noisy title into canonical role, seniority, department.
    
    Returns:
        (canonical_role, seniority, department) or (None, None, None) if no match
    """
    title_text = (str(headline) + " " + str(position)).lower()
    
    # Try to match against normalization patterns
    for pattern, canonical_role in ROLE_NORMALIZATION.items():
        if re.search(pattern, title_text):
            seniority = SENIORITY_MAPPING.get(canonical_role)
            department = DEPARTMENT_MAPPING.get(canonical_role)
            return canonical_role, seniority, department
    
    # No match found
    return None, None, None


# ============================================================
# STEP 6: EMAIL GENERATION WITH CONFIDENCE
# ============================================================

def extract_company_domain(email_format: str) -> Optional[str]:
    """Extract domain from email format pattern."""
    if not email_format or pd.isna(email_format):
        return None
    # Extract domain from patterns like "first.last@company.com"
    match = re.search(r'@([\w\.-]+)', str(email_format))
    return match.group(1) if match else None


def generate_email_with_confidence(
    first_name: str,
    last_name: str,
    email_format: str,
    potential_emails: str = None
) -> Tuple[Optional[str], float]:
    """
    Generate email with confidence score.
    
    Returns:
        (email, confidence) where confidence is 0.0-1.0
    """
    if not first_name or not last_name or pd.isna(first_name) or pd.isna(last_name):
        return None, 0.0
    
    first = str(first_name).strip().lower()
    last = str(last_name).strip().lower()
    
    if not first or not last:
        return None, 0.0
    
    # Extract company domain early (needed for fallback)
    domain = extract_company_domain(email_format)
    
    # Priority 1: Use email format from CSV (highest confidence)
    if email_format and not pd.isna(email_format) and domain:
        email = (
            str(email_format)
            .replace("{first}", first)
            .replace("{last}", last)
            .replace("{f}", first[0])
            .replace("{l}", last[0])
        )
        return email, 0.9  # Format confirmed
    
    # Priority 2: Extract from potential_emails (medium confidence)
    if potential_emails and not pd.isna(potential_emails):
        try:
            emails = ast.literal_eval(str(potential_emails))
            if isinstance(emails, list) and emails:
                return emails[0].strip(), 0.6  # Inferred
        except:
            pass
    
    # Priority 3: Fallback pattern (low confidence)
    if domain:
        # Use first.last format with the actual company domain
        email = f"{first}.{last}@{domain}"
        return email, 0.3
    
    return None, 0.0 # Cannot proceed without a domain


# ============================================================
# STEP 7: MAIN NORMALIZATION FUNCTION
# ============================================================

def normalize_for_outreach(
    raw_df: pd.DataFrame,
    company_name: str,
    email_format: str
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Transform raw StaffSpy output into outreach-ready data.
    
    Args:
        raw_df: Raw StaffSpy CSV DataFrame
        company_name: Company name (e.g., "Zepto")
        email_format: Email format pattern from target_companies.csv
    
    Returns:
        (outreach_ready_df, rejected_debug_df)
    """
    logging.info(f"\n{'='*70}")
    logging.info(f"NORMALIZING: {company_name} ({len(raw_df)} raw rows)")
    logging.info(f"{'='*70}\n")
    
    all_rejected = []
    
    # STEP 1: Hard filter invalid profiles
    valid_df, rejected_hard = hard_filter_invalid_profiles(raw_df)
    # Ensure rejected_hard has the rejection_reason column before appending
    if not rejected_hard.empty and "rejection_reason" not in rejected_hard.columns:
        rejected_hard["rejection_reason"] = "Structural hard filter"
    all_rejected.append(rejected_hard)
    
    if valid_df.empty:
        logging.warning("No valid profiles after hard filtering")
        rejected_all = pd.concat(all_rejected, ignore_index=True) if all_rejected else pd.DataFrame()
        return pd.DataFrame(columns=OUTREACH_SCHEMA), rejected_all
    
    # STEP 2: Role relevance filtering
    allowed_df, rejected_roles = filter_by_role_relevance(valid_df)
    all_rejected.append(rejected_roles)
    
    if allowed_df.empty:
        logging.warning("No relevant roles after filtering")
        rejected_all = pd.concat(all_rejected, ignore_index=True) if all_rejected else pd.DataFrame()
        return pd.DataFrame(columns=OUTREACH_SCHEMA), rejected_all
    
    # STEP 3: Normalize titles and generate outreach schema
    outreach_rows = []
    
    for idx, row in allowed_df.iterrows():
        # Normalize role
        headline = row.get("headline", "")
        position = row.get("position", "") or row.get("current_position", "")
        role, seniority, department = normalize_role(headline, position)
        
        if not role:
            # Capture rejection reason
            rejected_row = row.copy()
            rejected_row["rejection_reason"] = "Could not normalize role"
            all_rejected.append(pd.DataFrame([rejected_row]))
            continue
        
        # Generate email with confidence
        first_name = row.get("first_name", "")
        last_name = row.get("last_name", "")
        potential_emails = row.get("potential_emails", "")
        
        email, email_confidence = generate_email_with_confidence(
            first_name, last_name, email_format, potential_emails
        )
        
        if not email or email_confidence < 0.3: # Hard floor of 0.3 confidence for outreach
            # Capture rejection reason
            rejected_row = row.copy()
            rejected_row["rejection_reason"] = f"Low email confidence ({email_confidence})"
            all_rejected.append(pd.DataFrame([rejected_row]))
            continue
        
        # Extract company domain
        company_domain = extract_company_domain(email_format) or "unknown"
        
        # Build outreach-ready row
        outreach_row = {
            "company": company_name,
            "first_name": first_name,
            "last_name": last_name,
            "role": role,
            "seniority": seniority,
            "department": department,
            "linkedin_url": row.get("profile_link", ""),
            "company_domain": company_domain,
            "email": email,
            "email_confidence": email_confidence,
            "source": "LinkedIn_StaffSpy",
            # Preserve raw fields for scoring
            "profile_id": row.get("profile_id", ""),
            "followers": row.get("followers", 0),
            "connections": row.get("connections", 0),
            "is_hiring": row.get("is_hiring", False),
            "headline": row.get("headline", ""),
            "bio": row.get("bio", ""),
            "skills": row.get("skills", ""),
            "experiences": row.get("experiences", "")
        }
        
        outreach_rows.append(outreach_row)
    
    outreach_df = pd.DataFrame(outreach_rows)
    
    # Combine all rejected rows
    rejected_all = pd.concat(all_rejected, ignore_index=True) if all_rejected else pd.DataFrame()
    
    logging.info(f"\nNORMALIZATION COMPLETE")
    logging.info(f"   Outreach-ready: {len(outreach_df)} rows")
    logging.info(f"   Rejected: {len(rejected_all)} rows")
    
    # Avoid division by zero if raw_df is empty, although hard filtering should catch this
    if len(raw_df) > 0:
        conversion_rate = len(outreach_df) / len(raw_df) * 100
        logging.info(f"   Conversion rate: {conversion_rate:.1f}%")
    
    return outreach_df, rejected_all