# logger_setup.py
import os
import sys
from loguru import logger
from config import Config

os.makedirs("logs", exist_ok=True)

logger.remove()

# ── Console handler ───────────────────────────────────────────────────────────
logger.add(
    sys.stdout,
    colorize=True,
    level=Config.LOG_LEVEL,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
)

# ── File handler (no sensitive content at DEBUG in prod) ──────────────────────
logger.add(
    "logs/bot.log",
    rotation="1 day",
    retention="30 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    enqueue=True,       # thread-safe writes
    backtrace=True,
    diagnose=False,     # keep False in prod — prevents locals leaking to log
)

log = logger
