def extract_harvard_text(soup):
    """
    Harvard SEAS (Drupal) person pages
    """

    selectors = [
        ".field--name-field-person-research-summary",
        ".field--name-body",
        ".node__content",
        ".field--name-field-person-bio",
    ]

    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(" ", strip=True)
            if len(text) > 120:
                return text

    return ""