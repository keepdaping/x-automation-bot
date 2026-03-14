def score_tweet(metrics):

    score = (
        metrics.get("likes", 0) * 2
        + metrics.get("replies", 0) * 3
        + metrics.get("retweets", 0) * 2
    )

    # Boost recent tweets (favor tweets posted in the last few hours)
    age_seconds = metrics.get("age_seconds")
    if age_seconds is not None:
        age_hours = age_seconds / 3600
        if age_hours <= 1:
            score += 10
        elif age_hours <= 6:
            score += 5
        elif age_hours <= 24:
            score += 2

    return score