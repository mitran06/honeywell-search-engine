def is_valid_chunk(text: str) -> bool:
    if not text:
        return False

    # Allow abstracts & introductions
    if len(text.split()) < 25:
        return False

    blacklist = [
        "authorized licensed",
        "copyright",
        "all rights reserved"
    ]

    lower = text.lower()
    return not any(b in lower for b in blacklist)
