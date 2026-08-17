import logging
import re

import requests
import urllib3
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

from . import config

logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SERVICE_HEADING_KEYWORDS = ("service", "solution", "what we do", "expertise", "offerings")
PRODUCT_HEADING_KEYWORDS = ("product", "our range", "what we offer")

SERVICE_PATHS = ("/services", "/our-services")
PRODUCT_PATHS = ("/products", "/our-products")

MAX_ITEMS = 8
MAX_ITEM_LENGTH = 100

_session = requests.Session()
_session.headers.update(config.HEADERS)
_session.mount(
    "https://",
    HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503])),
)


def enrich_lead(company: dict) -> dict:
    result = {**company, "services": [], "products": []}

    website = company.get("website", "")
    html = _fetch(website)
    if html:
        soup = BeautifulSoup(html, "html.parser")
        result["services"] = _extract_by_keywords(soup, SERVICE_HEADING_KEYWORDS)
        result["products"] = _extract_by_keywords(soup, PRODUCT_HEADING_KEYWORDS)

    if not result["services"]:
        result["services"] = _try_paths(website, SERVICE_PATHS, SERVICE_HEADING_KEYWORDS)
    if not result["products"]:
        result["products"] = _try_paths(website, PRODUCT_PATHS, PRODUCT_HEADING_KEYWORDS)

    return result


def enrich_leads(companies: list[dict]) -> list[dict]:
    return [enrich_lead(c) for c in companies]


def _try_paths(website: str, paths: tuple, keywords: tuple) -> list[str]:
    for path in paths:
        html = _fetch(website.rstrip("/") + path)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        items = _extract_by_keywords(soup, keywords)
        if items:
            return items
    return []


def _extract_by_keywords(soup: BeautifulSoup, keywords: tuple) -> list[str]:
    found: list[str] = []
    for heading in soup.find_all(["h2", "h3", "h4"]):
        heading_text = heading.get_text(strip=True).lower()
        if not any(kw in heading_text for kw in keywords):
            continue

        sibling = heading.find_next_sibling(["ul", "ol"])
        if not sibling:
            continue

        for li in sibling.find_all("li"):
            item = li.get_text(strip=True)
            if item and len(item) <= MAX_ITEM_LENGTH and item not in found:
                found.append(item)

        if len(found) >= MAX_ITEMS:
            break

    return found[:MAX_ITEMS]


def _fetch(url: str) -> str | None:
    if not url:
        return None
    try:
        response = _session.get(url, timeout=config.EXTRACTION_TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.SSLError:
        try:
            response = _session.get(url, timeout=config.EXTRACTION_TIMEOUT, verify=False)
            response.raise_for_status()
        except requests.RequestException:
            return None
    except requests.RequestException:
        return None
    return response.text