def score_tweet(metrics):

    score = (
        metrics["likes"] * 2
        + metrics["replies"] * 3
        + metrics["retweets"] * 2
    )

    return score