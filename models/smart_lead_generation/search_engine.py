import logging
import math
import re
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter, Retry

from . import config

logger = logging.getLogger(__name__)

DIRECTORY_DOMAINS = {
    "justdial.com", "indiamart.com", "sulekha.com", "yellowpages.com",
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com",
    "wikipedia.org", "youtube.com", "glassdoor.com", "quora.com",
    "google.com", "f6s.com", "clutch.co", "ambitionbox.com",
    "proptiger.com", "propi.in", "indextap.com",
    "scribd.com", "naukri.com", "colive.com", "salezshark.com", "skillogic.com",
    "99acres.com", "magicbricks.com", "housing.com", "commonfloor.com",
    "realestateindia.com", "real-locator.com",
}

LISTICLE_TITLE_PATTERN = re.compile(
    r"^(\d+\s+)?(top|best|list|industry|what|how|why|which|who)\b|\?$",
    re.IGNORECASE,
)

MAX_TOTAL_SEARCH_CALLS = 60

_session = requests.Session()
_session.mount(
    "https://",
    HTTPAdapter(max_retries=Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503])),
)


def search_companies(location: str, industry: str, num_leads: int) -> list[dict]:
    if num_leads <= 0:
        return []

    leads: list[dict] = []
    seen_domains: set[str] = set()
    calls_used = 0

    for query in _build_queries(location, industry):
        if len(leads) >= num_leads or calls_used >= MAX_TOTAL_SEARCH_CALLS:
            break
        calls_used = _collect_from_query(query, location, num_leads, leads, seen_domains, calls_used)

    if len(leads) < num_leads:
        logger.warning(
            "Requested %d leads but only found %d after %d search calls "
            "across all query variations - genuinely exhausted available results.",
            num_leads, len(leads), calls_used,
        )
    else:
        logger.info(
            "Found %d/%d requested leads using %d search calls.",
            len(leads), num_leads, calls_used,
        )

    return leads[:num_leads]


def _build_queries(location: str, industry: str) -> list[str]:
    return [
        f"{industry} companies in {location}",
        f"top {industry} businesses {location}",
        f"{industry} developers in {location}",
        f"leading {industry} firms {location}",
        f"best {industry} companies {location}",
        f"{industry} services {location}",
    ]


def _collect_from_query(
    query: str, location: str, num_leads: int, leads: list[dict], seen_domains: set[str], calls_used: int
) -> int:
    pages_needed = math.ceil(num_leads / config.RESULTS_PER_PAGE)
    max_pages = min(pages_needed, config.MAX_PAGES_SAFETY_LIMIT)

    for page in range(max_pages):
        if len(leads) >= num_leads or calls_used >= MAX_TOTAL_SEARCH_CALLS:
            return calls_used

        results = _google_search(query, start=page * config.RESULTS_PER_PAGE)
        calls_used += 1
        if not results:
            return calls_used

        for result in results:
            domain = _extract_domain(result.get("link", ""))
            title = result.get("title", "")

            if not domain or domain in seen_domains or _is_junk(domain, title):
                continue

            leads.append({
                "company_name": _clean_title(title),
                "website": f"https://{domain}",
                "location": location,
            })
            seen_domains.add(domain)

            if len(leads) >= num_leads:
                return calls_used

    return calls_used


def _is_junk(domain: str, title: str) -> bool:
    if any(domain == d or domain.endswith(f".{d}") for d in DIRECTORY_DOMAINS):
        return True
    if LISTICLE_TITLE_PATTERN.search(title.strip()):
        return True
    return False


def _google_search(query: str, start: int = 0) -> list[dict]:
    params = {
        "q": query,
        "api_key": config.SERPAPI_KEY,
        "engine": "google",
        "start": start,
    }
    try:
        response = _session.get(config.SERPAPI_URL, params=params, timeout=config.REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException:
        # not logging the exception directly, it embeds the api key in the url
        logger.error("SerpApi request failed for query=%r start=%d", query, start)
        return []

    return response.json().get("organic_results", [])


def _extract_domain(url: str) -> str:
    netloc = urlparse(url).netloc
    return netloc[4:] if netloc.startswith("www.") else netloc


def _clean_title(title: str) -> str:
    for separator in (" - ", " | ", ": "):
        if separator in title:
            return title.split(separator)[0].strip()
    return title.strip()