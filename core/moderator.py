# core/moderator.py
import re
from config import Config
from database import is_duplicate

def is_safe_content(text: str) -> bool:
    """Basic content safety checks"""
    if len(text.strip()) < 40 or len(text) > 280:
        return False

    text_lower = text.lower()
    if any(word in text_lower for word in Config.BANNED_WORDS):
        return False

    # Very basic spam pattern check
    if re.search(r'(http|https)://\S+', text) and "…" not in text:
        return False  # links without ellipsis usually look spammy

    return True


def score_content_quality(critique_response: str) -> float:
    """Extract numeric score from Sonnet critique (very naive parser)"""
    import re
    match = re.search(r'(\d+\.?\d*)\s*/\s*10', critique_response)
    if match:
        try:
            return float(match.group(1))
        except:
            pass
    # fallback heuristic
    if "excellent" in critique_response.lower() or "viral" in critique_response.lower():
        return 9.0
    if "good" in critique_response.lower():
        return 7.5
    return 6.0