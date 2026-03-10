# core/replier.py
# (simplified version — can be extended later)

def should_reply_to(text: str) -> bool:
    text = text.lower()
    return len(text.split()) >= 12 or "?" in text


def generate_reply_text(parent_text: str) -> str | None:
    # Similar structure to generate_quote_text
    # For brevity — reuse same logic or extend
    return None   # placeholder — implement analogously to quote