# main.py
from auth import get_client
from config import Config
from logger_setup import log
from database import init_db
from core.generator import generate_post
from core.poster import post_tweet
from core.thread_generator import generate_thread
from core.thread_poster import post_thread
from core.quoter import find_quote_candidate, generate_quote_text


def main():
    log.info("X Growth Bot — starting one-shot run")
    init_db()

    try:
        Config.validate()
        client = get_client()
    except Exception as e:
        log.critical(f"Startup failed: {e}")
        return 1

    # Decide what to do this run
    from datetime import datetime
    run_minute = datetime.now().minute

    if run_minute % 15 == 0:   # roughly every 4th run → thread
        topic = Config.pick_topic()
        thread = generate_thread(topic)
        if thread:
            post_thread(client, thread)
    elif run_minute % 7 == 3:   # quote tweet ~once per day
        orig_id = find_quote_candidate(client)
        if orig_id:
            orig_tweet = client.get_tweet(orig_id).data
            quote_text = generate_quote_text(orig_tweet.text)
            if quote_text:
                client.create_tweet(text=quote_text, quote_tweet_id=orig_id)
                log.info("Quote tweet posted")
    else:
        topic = Config.pick_topic()
        fmt = Config.pick_format()
        text, source, score = generate_post(topic, fmt)
        post_tweet(client, text, topic, fmt, score)

    log.info("Run complete.")
    return 0




if __name__ == "__main__":
    exit(main())