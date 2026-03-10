# core/thread_generator.py
# (very similar to generator.py but asks for 4 connected tweets)

def generate_thread(topic: str) -> list[str] | None:
    client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    weekday = time.strftime("%A")

    system = f"""{_SYSTEM_BASE.format(weekday=weekday)}

This is the FIRST tweet of a 4-tweet thread.
Write strong hook + context + promise of value.
Number tweets implicitly (1/4, 2/4 etc.) at beginning of each.
Output format: four lines separated by ---"""

    try:
        msg = client.messages.create(
            model=Config.AI_MODEL_CRITIQUE,  # better model for threads
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": f"Topic: {topic}"}]
        )
        content = msg.content[0].text.strip()
        parts = [p.strip() for p in content.split("---") if p.strip()]
        if len(parts) != 4:
            return None
        return parts
    except Exception as e:
        log.error(f"Thread generation failed: {e}")
        return None