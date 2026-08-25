import logging

import requests
from requests.adapters import HTTPAdapter, Retry

from . import config

logger = logging.getLogger(__name__)

_session = requests.Session()
_session.mount(
    "https://",
    HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503])),
)


def lookup_rating(company: dict) -> dict:
    result = {**company, "maps_rating": None, "maps_reviews_count": None}

    company_name = company.get("company_name")
    location = company.get("location", "")
    if not company_name:
        return result

    query = f"{company_name} {location}"
    params = {
        "engine": "google_maps",
        "q": query,
        "type": "search",
        "api_key": config.SERPAPI_KEY,
    }
    try:
        response = _session.get(config.SERPAPI_URL, params=params, timeout=config.REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException:
        logger.error("Maps rating lookup failed for %r", company_name)
        return result

    places = response.json().get("local_results", [])
    if not places:
        return result

    best_match = places[0]
    result["maps_rating"] = best_match.get("rating")
    result["maps_reviews_count"] = best_match.get("reviews")
    return result


def lookup_ratings(companies: list[dict]) -> list[dict]:
    return [lookup_rating(c) for c in companies]