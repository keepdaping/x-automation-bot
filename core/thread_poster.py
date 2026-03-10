# core/thread_poster.py
def post_thread(client, tweets: list[str]) -> list[str]:
    ids = []
    previous_id = None

    for i, text in enumerate(tweets, 1):
        try:
            time.sleep(random.uniform(12, 45))
            resp = client.create_tweet(
                text=text,
                in_reply_to_tweet_id=previous_id
            )
            tweet_id = resp.data["id"]
            ids.append(tweet_id)
            previous_id = tweet_id
            log.info(f"Thread part {i}/{len(tweets)} → {tweet_id}")
        except Exception as e:
            log.error(f"Thread posting failed at part {i}: {e}")
            break

    return ids