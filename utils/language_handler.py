"""Language detection for tweet filtering."""

from typing import Tuple, Optional
from logger_setup import log

try:
    from langdetect import detect, detect_langs, LangDetectException
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False

try:
    from textblob import TextBlob
    HAS_TEXTBLOB = True
except ImportError:
    HAS_TEXTBLOB = False


class LanguageHandler:
    LANGUAGE_NAMES = {
        'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German',
        'pt': 'Portuguese', 'ja': 'Japanese', 'zh': 'Chinese', 'ar': 'Arabic',
    }

    @staticmethod
    def detect_language(text: str) -> Tuple[str, float]:
        try:
            if HAS_LANGDETECT:
                try:
                    lang_code = detect(text)
                    langs = detect_langs(text)
                    confidence = max([x.prob for x in langs])
                    return lang_code, confidence
                except LangDetectException:
                    pass
            if HAS_TEXTBLOB:
                blob = TextBlob(text)
                return blob.detect_language(), 0.8
            return 'en', 0.5
        except Exception:
            return 'en', 0.5

    @staticmethod
    def should_reply_to_tweet(text: str) -> Tuple[bool, Optional[str]]:
        lang_code, confidence = LanguageHandler.detect_language(text)
        # Allow English at any confidence — langdetect is unreliable on short/
        # hashtag-heavy text and would silently block valid English tweets.
        if lang_code == 'en':
            return True, None
        # Non-English: only block if confidence is high enough to be trustworthy
        if confidence >= 0.80:
            lang_name = LanguageHandler.LANGUAGE_NAMES.get(lang_code, lang_code.upper())
            return False, f"Non-English: {lang_name} ({confidence:.2f})"
        # Low-confidence non-English → allow through (better to reply than miss)
        return True, None


def should_reply_to_tweet_safe(tweet_text: str) -> Tuple[bool, Optional[str]]:
    should_reply, reason = LanguageHandler.should_reply_to_tweet(tweet_text)
    if not should_reply:
        log.info(f"⏭️  Skipping: {reason}")
    return should_reply, reason
