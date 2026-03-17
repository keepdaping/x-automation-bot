"""Centralized DOM selectors for X.com"""

TWEET_ARTICLE = "article"
TWEET_TEXT = "[data-testid='tweetText']"
TWEET_TIMESTAMP = "[role='link'][href*='/status/']"

LIKE_BUTTON = "[data-testid='like']"
REPLY_BUTTON = "[data-testid='reply']"
RETWEET_BUTTON = "[data-testid='retweet']"
FOLLOW_BUTTON = "[data-testid='follow']"

REPLY_TEXTAREA = "[data-testid='tweetTextarea_0']"
COMPOSE_BOX = "[data-testid='tweetButton']"

SEARCH_RESULTS_CONTAINER = "[data-testid='primaryColumn']"
TIMELINE_ITEM = "[data-testid='tweet']"

LIKE_COUNT = "[data-testid='like'] span"
REPLY_COUNT = "[data-testid='reply'] span"
RETWEET_COUNT = "[data-testid='retweet'] span"
