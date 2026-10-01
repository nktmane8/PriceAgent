"""Global constants: fixed values shared by many modules. They do NOT change between environments.
(Values that DO change per environment, such as URLs, limits and keys, live in config.py / env files.)"""
import re

# ---- job lifecycle and kinds -------------------------------------------------
QUEUED, RUNNING, DONE, ERROR = "queued", "running", "done", "error"
ACTIVE = (QUEUED, RUNNING)          # job still working
FINISHED = (DONE, ERROR)            # job will not change any more
KIND_PRICES, KIND_INSIGHTS = "prices", "insights"
KINDS = (KIND_PRICES, KIND_INSIGHTS)

# ---- input validation --------------------------------------------------------
PRODUCT_MIN, PRODUCT_MAX = 3, 120
PLACE_MIN, PLACE_MAX = 2, 60        # country and city length
MAX_SITES = 8
PLACE_RE = re.compile(r"^[\w\s.,'&()-]{2,60}$")                 # letters, digits, basic punctuation only
DOMAIN_RE = re.compile(r"^[a-z0-9.-]{3,60}\.[a-z]{2,}$")        # plain domains like example.com

# ---- time windows (seconds) --------------------------------------------------
HOUR = 3600
LOGIN_WINDOW = 900                  # 15 minutes
PURGE_INTERVAL = 600                # purge thread cadence
JOB_RETENTION_DAYS = 7
USAGE_RETENTION_DAYS = 1
HISTORY_DAYS = 90                   # window shown to users
HISTORY_RETENTION_DAYS = 180        # how long history rows are kept

# ---- OAuth -------------------------------------------------------------------
SCOPE = "prices:read"
ACCESS_TTL, REFRESH_TTL = 3600, 30 * 86400
CODE_TTL, AUTHREQ_TTL = 600, 900
LOGIN_IP_LIMIT, LOGIN_ACCOUNT_LIMIT = 30, 10    # attempts per LOGIN_WINDOW
TOKEN_IP_LIMIT, REGISTER_IP_LIMIT = 120, 20     # per hour
PASSWORD_MIN = 10

# ---- caps on model output (anti-corruption layer) ---------------------------------
MAX_RESULTS, MAX_OFFERS = 12, 8
MAX_REVIEWS, MAX_ALTERNATIVES = 10, 5
STORE_TYPES = ("marketplace", "brand", "chain", "local")
REVIEW_SOURCE_TYPES = ("publication", "video", "user")

# ---- cost estimate --------------------------------------------------------------------
SEARCH_COST_USD = 0.01              # Anthropic web search list price when written ($10 per 1,000); verify
