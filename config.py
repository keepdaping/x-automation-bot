


:::writing{variant="standard" id="cfg02"}
import os


class Config:

    # API KEY
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

    # AI models
    AI_MODEL_DRAFT = "claude-3-haiku-20240307"
    AI_MODEL_CRITIQUE = "claude-3-sonnet-20240229"

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
:::

**Important:**  
Make sure the file **contains no ``` characters**.

---

# Then run the bot again
