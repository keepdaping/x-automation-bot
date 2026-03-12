import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    # API KEY
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

    # AI models - tries these in order, uses first one that works
    # List of models to try when generating replies
    AI_MODELS_TO_TRY = [
        "claude-opus-4-1",
        "claude-opus-4",
        "claude-3-opus-20240229",
        "claude-3.5-sonnet",
        "claude-3-5-sonnet-20241022",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ]
    
    # Default to first model (will try in order if it fails)
    AI_MODEL_DRAFT = AI_MODELS_TO_TRY[0]
    AI_MODEL_CRITIQUE = AI_MODELS_TO_TRY[0]

    # AI limits
    AI_MAX_TOKENS = 200
    AI_MAX_RETRIES = 3

    # engagement limits per run
    MAX_LIKES_PER_RUN = 8
    MAX_REPLIES_PER_RUN = 4
    MAX_QUOTES_PER_RUN = 2

    # viral detection thresholds
    MIN_LIKES_FOR_VIRAL = 20
    MIN_REPLIES_FOR_VIRAL = 3

    # human behavior delays
    MIN_DELAY = 20
    MAX_DELAY = 90
