
def summarize_text(text):
    """Return a short extract from the supplied text."""
    if not text or not text.strip():
        return ""

    sentences = [
        sentence.strip()
        for sentence in text.replace("\n", " ").split(".")
        if sentence.strip()
    ]

    return ". ".join(sentences[:2]) + ("." if sentences else "")
