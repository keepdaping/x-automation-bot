"""
Language detection and intelligent reply handling for non-English tweets.

This module:
1. Detects tweet language
2. Skips or translates non-English tweets
3. Generates contextually appropriate replies
4. Maintains human-like behavior
"""

import os
from typing import Tuple, Optional
from logger_setup import log

# Try to import language detection libraries
try:
    from textblob import TextBlob
    HAS_TEXTBLOB = True
except ImportError:
    HAS_TEXTBLOB = False
    log.warning("textblob not installed - language detection disabled")

try:
    from langdetect import detect, detect_langs, LangDetectException
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False
    log.warning("langdetect not installed - language detection disabled")


class LanguageHandler:
    """Handles language detection, skipping, and translation for tweets"""
    
    # English-speaking locales (user only replies in these languages)
    SUPPORTED_LANGUAGES = {
        'en': 'English',
    }
    
    # Maps of language codes to full names  
    LANGUAGE_NAMES = {
        'en': 'English',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'pt': 'Portuguese',
        'ja': 'Japanese',
        'zh': 'Chinese',
        'ar': 'Arabic',
        'ru': 'Russian',
        'ha': 'Hausa',
    }
    
    @staticmethod
    def detect_language(text: str) -> Tuple[str, float]:
        """
        Detect language of text.
        
        Returns:
            (language_code, confidence)
            Examples: ('en', 0.99), ('es', 0.85), ('ha', 0.92)
        """
        try:
            # Try langdetect first (more accurate for non-European languages)
            if HAS_LANGDETECT:
                try:
                    lang_code = detect(text)
                    # Get confidence
                    langs = detect_langs(text)
                    confidence = max([x.prob for x in langs])
                    return lang_code, confidence
                except LangDetectException as e:
                    log.debug(f"langdetect failed: {e}, trying textblob")
            
            # Fallback to textblob
            if HAS_TEXTBLOB:
                blob = TextBlob(text)
                lang_code = blob.detect_language()
                # TextBlob doesn't give confidence, assume 0.8
                return lang_code, 0.8
            
            # Default to English if no detection available
            log.warning("No language detection available, assuming English")
            return 'en', 0.5
            
        except Exception as e:
            log.error(f"Language detection error: {e}")
            return 'en', 0.5  # Default to English on error

    @staticmethod
    def is_english(text: str, min_confidence: float = 0.7) -> bool:
        """
        Check if text is in English.
        
        Args:
            text: Tweet text to check
            min_confidence: Minimum confidence threshold (0-1)
        
        Returns:
            True if detected as English with sufficient confidence
        """
        lang_code, confidence = LanguageHandler.detect_language(text)
        
        # Log non-English detection
        if lang_code != 'en':
            lang_name = LanguageHandler.LANGUAGE_NAMES.get(lang_code, lang_code.upper())
            log.info(f"Non-English tweet detected: {lang_name} (confidence: {confidence:.2f})")
        
        return lang_code == 'en' and confidence >= min_confidence

    @staticmethod
    def get_language_name(lang_code: str) -> str:
        """Get human-readable language name"""
        return LanguageHandler.LANGUAGE_NAMES.get(lang_code, lang_code.upper())

    @staticmethod
    def should_reply_to_tweet(text: str) -> Tuple[bool, Optional[str]]:
        """
        Determine if bot should reply to this tweet.
        
        Returns:
            (should_reply, reason)
            Examples:
            - (True, None) - English tweet, OK to reply
            - (False, "Non-English: Spanish") - Non-English, skip
            - (False, "Low confidence") - Unclear language, skip for safety
        """
        lang_code, confidence = LanguageHandler.detect_language(text)
        
        # High confidence English - reply
        if lang_code == 'en' and confidence >= 0.85:
            return True, None
        
        # Medium confidence English - reply but be cautious
        if lang_code == 'en' and confidence >= 0.70:
            log.debug(f"Medium confidence English ({confidence:.2f}), replying anyway")
            return True, None
        
        # English but low confidence - skip for safety
        if lang_code == 'en' and confidence < 0.70:
            return False, f"Low English confidence: {confidence:.2f}"
        
        # Non-English - skip (most human-like behavior)
        lang_name = LanguageHandler.LANGUAGE_NAMES.get(lang_code, lang_code.upper())
        return False, f"Non-English: {lang_name}"


def should_reply_to_tweet_safe(tweet_text: str) -> Tuple[bool, Optional[str]]:
    """
    Public API: Check if bot should reply to tweet based on language.
    
    Usage:
        should_reply, reason = should_reply_to_tweet_safe(tweet_text)
        if not should_reply:
            log.info(f"Skipping tweet: {reason}")
            return
    """
    should_reply, reason = LanguageHandler.should_reply_to_tweet(tweet_text)
    
    if not should_reply:
        log.info(f"⏭️  Skipping non-English tweet: {reason}")
    
    return should_reply, reason


def detect_tweet_language(tweet_text: str) -> str:
    """
    Public API: Detect language of tweet.
    
    Returns language code (e.g., 'en', 'es', 'fr', 'ha')
    """
    lang_code, confidence = LanguageHandler.detect_language(tweet_text)
    lang_name = LanguageHandler.get_language_name(lang_code)
    log.debug(f"Detected language: {lang_name} (code: {lang_code}, confidence: {confidence:.2f})")
    return lang_code
