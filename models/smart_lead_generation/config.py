import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]  # AI_ENGINE/
load_dotenv(ROOT_DIR / ".env")

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
if not SERPAPI_KEY:
    raise RuntimeError("SERPAPI_KEY environment variable is not set")

SERPAPI_URL = "https://serpapi.com/search"

RESULTS_PER_PAGE = 10

MAX_PAGES_SAFETY_LIMIT = 30

REQUEST_TIMEOUT = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
EXTRACTION_TIMEOUT = 10
BLOCKED_PAGE_MARKERS = ("access denied", "reference #", "captcha", "cloudflare", "akamai")