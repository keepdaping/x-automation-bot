"""
Centralized DOM selectors for X.com
Update these if X changes their DOM structure
"""

# Tweet elements
TWEET_ARTICLE = "article"
TWEET_TEXT = "[data-testid='tweetText']"
TWEET_TIMESTAMP = "[role='link'][href*='/status/']"

# Action buttons
LIKE_BUTTON = "[data-testid='like']"
REPLY_BUTTON = "[data-testid='reply']"
RETWEET_BUTTON = "[data-testid='retweet']"
QUOTE_BUTTON = "[data-testid='quote']"
FOLLOW_BUTTON = "[data-testid='follow']"
MORE_OPTIONS = "[data-testid='more']"

# Compose/Reply elements
REPLY_TEXTAREA = "[data-testid='tweetTextarea_0']"
COMPOSE_BOX = "[data-testid='tweetButton']"
POST_BUTTON = "[data-testid='tweetButtonInline']"
REPLY_TEXT_INPUT = "div[role='textbox']"

# Navigation
HOME_LINK = "[aria-label='Home']"
SEARCH_INPUT = "input[aria-label='Search post']"
PROFILE_MENU = "[data-testid='SideNav_NewTweet_Button']"

# Modals & overlays
COOKIE_CONSENT_MASK = "[data-testid='twc-cc-mask']"
DIALOG = "[role='dialog']"
MODAL_CLOSE = "[aria-label='Close']"

# Search results
SEARCH_RESULTS_CONTAINER = "[data-testid='primaryColumn']"
TIMELINE_ITEM = "[data-testid='tweet']"

# User info
USER_FOLLOW_BTN = "[data-testid='follow']"
USER_NAME = "[data-testid='user-name']"

# Metrics
LIKE_COUNT = "[data-testid='like'] span"
REPLY_COUNT = "[data-testid='reply'] span"
RETWEET_COUNT = "[data-testid='retweet'] span"
VIEW_COUNT = "[role='link'][aria-label*='views']"

# Notifications
NOTIFICATION_BADGE = "[data-testid='Icon_Notification_Active']"

# Alerts/errors  
ERROR_MESSAGE = "[role='alert']"
CONFIRM_DELETE = "[data-testid='confirmationSheetConfirm']"
