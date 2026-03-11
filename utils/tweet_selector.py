import time

def select_best_tweets(tweet_data, limit=5):
    """
    tweet_data = [
        {"tweet": tweet_element, "likes": 40, "replies": 5, "retweets": 3, "age_minutes": 20}
    ]
    """

    scored = []

    for item in tweet_data:

        # engagement score
        score = (
            item["likes"] * 2 +
            item["replies"] * 3 +
            item["retweets"] * 2
        )

        # freshness bonus
        if item["age_minutes"] < 60:
            score += 20

        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [x[1]["tweet"] for x in scored[:limit]]