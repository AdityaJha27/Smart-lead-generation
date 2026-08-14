import json as _json
import logging
import re

import requests
import urllib3
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

from . import config

logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

FOUNDED_PATTERN = re.compile(r"\b(?:founded|established|started)\s+(?:in\s+)?(\d{4})\b", re.IGNORECASE)
EMPLOYEE_PATTERN = re.compile(r"([\d,]+)\+?\s+(?:employees|team members|staff)", re.IGNORECASE)
SOCIAL_DOMAINS = ("linkedin.com", "twitter.com", "x.com", "facebook.com", "instagram.com", "youtube.com")

SOCIAL_LINK_JUNK_MARKERS = (
    "share", "sharer", "intent", "/login", "signin", "sign-in",
    "youtube.com/embed", "youtube.com/watch",
)

_session = requests.Session()
_session.headers.update(config.HEADERS)
_session.mount(
    "https://",
    HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503])),
)


def extract_company(company: dict) -> dict:
    result = {
        **company,
        "about": None,
        "founded": None,
        "employees": None,
        "social_media": [],
    }

    html = _fetch_page(company.get("website", ""))
    if not html:
        return result

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    jsonld = _extract_jsonld(soup)

    result["company_name"] = _clean_jsonld_name(jsonld.get("name")) or company.get("company_name")

    result["about"] = jsonld.get("description") or _extract_about(soup)
    result["founded"] = _clean_founded_year(jsonld.get("foundingDate")) or _first_match(FOUNDED_PATTERN, text)
    result["employees"] = (
        _sane_employee_count(jsonld.get("numberOfEmployees"))
        or _sane_employee_count(_first_match(EMPLOYEE_PATTERN, text, strip_commas=True))
    )
    result["social_media"] = _extract_social_links(soup)

    return result


def extract_companies(companies: list[dict]) -> list[dict]:
    return [extract_company(c) for c in companies]


def _fetch_page(url: str) -> str | None:
    if not url:
        return None

    try:
        response = _session.get(url, timeout=config.EXTRACTION_TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.SSLError:
        logger.warning("SSL verify failed for %s, retrying without verification", url)
        try:
            response = _session.get(url, timeout=config.EXTRACTION_TIMEOUT, verify=False)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.warning("Failed to fetch %s even without SSL verification: %s", url, e)
            return None
    except requests.RequestException as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None

    if _looks_blocked(response.text):
        logger.info("Bot-protection detected, skipping %s", url)
        return None

    return response.text


def _looks_blocked(html: str) -> bool:
    lowered = html[:3000].lower()
    return any(marker in lowered for marker in config.BLOCKED_PAGE_MARKERS)


def _extract_jsonld(soup: BeautifulSoup) -> dict:
    # reads Organization schema if the site has it
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = _json.loads(tag.string or "")
        except (ValueError, TypeError):
            continue
        for entry in (data if isinstance(data, list) else [data]):
            if isinstance(entry, dict) and entry.get("@type") in ("Organization", "Corporation", "LocalBusiness"):
                return entry
    return {}


def _clean_jsonld_name(value) -> str | None:
    if not value or not isinstance(value, str):
        return None
    cleaned = value.strip()
    if len(cleaned) < 2 or cleaned.lower() in ("home", "homepage", "welcome", "untitled"):
        return None
    return cleaned


def _clean_founded_year(value) -> str | None:
    if not value:
        return None
    match = re.search(r"(\d{4})", str(value))
    return match.group(1) if match else None


def _sane_employee_count(value) -> str | None:
    if not value:
        return None
    try:
        num = int(str(value).replace(",", ""))
    except ValueError:
        return None
    return str(num) if num > 0 else None


def _extract_about(soup: BeautifulSoup) -> str | None:
    meta = soup.find("meta", attrs={"name": "description"})
    if not meta or not meta.get("content"):
        meta = soup.find("meta", attrs={"property": "og:description"})

    if meta and meta.get("content"):
        return meta["content"].strip()

    paragraph = soup.find("p")
    return paragraph.get_text(strip=True)[:300] if paragraph else None


def _extract_social_links(soup: BeautifulSoup) -> list[str]:
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        lowered = href.lower()
        if not any(domain in lowered for domain in SOCIAL_DOMAINS):
            continue
        if any(marker in lowered for marker in SOCIAL_LINK_JUNK_MARKERS):
            continue
        links.add(href)
    return sorted(links)


def _first_match(pattern: re.Pattern, text: str, strip_commas: bool = False) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1).replace(",", "") if strip_commas else match.group(1)