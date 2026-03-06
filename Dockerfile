# ── Builder stage ────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install dependencies into an isolated prefix so we can copy cleanly
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

LABEL org.opencontainers.image.title="x-automation-bot"
LABEL org.opencontainers.image.description="AI-powered X content bot using Claude + Tweepy"

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash botuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY --chown=botuser:botuser . .

# Persistent volumes for data and logs
RUN mkdir -p /app/data /app/logs && chown -R botuser:botuser /app/data /app/logs

USER botuser

# Healthcheck — confirms the process is still alive
HEALTHCHECK --interval=5m --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f "python main.py" || exit 1

CMD ["python", "main.py"]
