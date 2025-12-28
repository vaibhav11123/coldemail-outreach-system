def extract_generic_text(soup):
    """
    Works for Berkeley, UCLA, UIUC, MIT-style pages
    """
    candidates = []

    # Common research headers
    for header in ["Research", "Research Interests", "Research Areas"]:
        h = soup.find(
            lambda tag: tag.name in ["h2", "h3"]
            and header.lower() in tag.get_text().lower()
        )
        if h:
            p = h.find_next("p")
            if p and len(p.get_text(strip=True)) > 100:
                return p.get_text(" ", strip=True)

    # Fallback: largest paragraph
    for p in soup.find_all("p"):
        t = p.get_text(strip=True)
        if len(t) > 120:
            candidates.append(t)

    return max(candidates, key=len) if candidates else ""