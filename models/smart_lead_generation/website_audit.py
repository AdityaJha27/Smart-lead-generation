import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

from . import config

logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MAX_WORKERS = 10
MAX_LINKS_TO_CHECK = 8
LINK_CHECK_TIMEOUT = 5
STALE_CONTENT_YEARS = 2
SLOW_LOAD_THRESHOLD_SECONDS = 3.0

COPYRIGHT_YEAR_PATTERN = re.compile(r"(?:©|copyright)\s*\D{0,10}(\d{4})", re.IGNORECASE)
OLD_JQUERY_PATTERN = re.compile(r"jquery[-/.]1\.\d", re.IGNORECASE)

_session = requests.Session()
_session.headers.update(config.HEADERS)
_session.mount(
    "https://",
    HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503])),
)


def audit_website(company: dict) -> dict:
    result = {**company, "has_website": False, "website_audit": None}

    website = company.get("website", "")
    if not website:
        return result

    result["has_website"] = True
    start = time.monotonic()
    html = _fetch(website)
    load_time_seconds = round(time.monotonic() - start, 2)

    if not html:
        result["website_audit"] = {
            "uses_https": website.lower().startswith("https://"),
            "reachable": False,
            "issues": ["Website did not respond or could not be fetched"],
            "issue_count": 1,
        }
        return result

    soup = BeautifulSoup(html, "html.parser")

    uses_https = website.lower().startswith("https://")
    seo_title_present = bool(soup.title and soup.title.get_text(strip=True))
    seo_meta_description_present = bool(soup.find("meta", attrs={"name": "description"}))
    h1_count = len(soup.find_all("h1"))
    mobile_responsive = bool(soup.find("meta", attrs={"name": "viewport"}))
    outdated_tech_stack = bool(OLD_JQUERY_PATTERN.search(html))

    content_last_updated_year = _extract_copyright_year(soup)
    content_is_stale = (
        content_last_updated_year is not None
        and (datetime.now(timezone.utc).year - content_last_updated_year) >= STALE_CONTENT_YEARS
    )

    alt_text_percentage = _image_alt_text_percentage(soup)
    broken_links_checked, broken_links_found, broken_links_inconclusive = _check_internal_links(website, soup)

    issues = []
    if not uses_https:
        issues.append("Not using HTTPS/SSL")
    if not seo_title_present:
        issues.append("Missing page title")
    if not seo_meta_description_present:
        issues.append("Missing meta description")
    if h1_count == 0:
        issues.append("No H1 heading found")
    elif h1_count > 1:
        issues.append("Multiple H1 headings (SEO structure issue)")
    if not mobile_responsive:
        issues.append("No mobile viewport tag - likely not mobile-responsive")
    if outdated_tech_stack:
        issues.append("References an outdated jQuery version")
    if content_is_stale:
        issues.append(f"Content appears stale (copyright year {content_last_updated_year})")
    if alt_text_percentage is not None and alt_text_percentage < 50:
        issues.append(f"Only {alt_text_percentage:.0f}% of images have alt text")
    if broken_links_inconclusive:
        issues.append("Could not verify internal links - site may be blocking automated checks")
    elif broken_links_found > 0:
        issues.append(f"{broken_links_found}/{broken_links_checked} checked links are broken")
    if load_time_seconds > SLOW_LOAD_THRESHOLD_SECONDS:
        issues.append(f"Slow page load time ({load_time_seconds}s)")

    result["website_audit"] = {
        "uses_https": uses_https,
        "reachable": True,
        "load_time_seconds": load_time_seconds,
        "seo_title_present": seo_title_present,
        "seo_meta_description_present": seo_meta_description_present,
        "h1_count": h1_count,
        "mobile_responsive": mobile_responsive,
        "outdated_tech_stack": outdated_tech_stack,
        "content_last_updated_year": content_last_updated_year,
        "content_is_stale": content_is_stale,
        "image_alt_text_percentage": alt_text_percentage,
        "broken_links_checked": broken_links_checked,
        "broken_links_found": broken_links_found,
        "broken_links_inconclusive": broken_links_inconclusive,
        "issues": issues,
        "issue_count": len(issues),
    }
    return result


def audit_websites(companies: list[dict]) -> list[dict]:
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        return list(executor.map(audit_website, companies))


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


def _extract_copyright_year(soup: BeautifulSoup) -> int | None:
    text = soup.get_text(" ", strip=True)
    matches = COPYRIGHT_YEAR_PATTERN.findall(text)
    years = [int(y) for y in matches if 1990 <= int(y) <= datetime.now(timezone.utc).year]
    return max(years) if years else None


def _image_alt_text_percentage(soup: BeautifulSoup) -> float | None:
    images = soup.find_all("img")
    if not images:
        return None
    with_alt = sum(1 for img in images if img.get("alt", "").strip())
    return round((with_alt / len(images)) * 100, 1)


def _check_internal_links(base_url: str, soup: BeautifulSoup) -> tuple[int, int, bool]:
    base_domain = urlparse(base_url).netloc.lower()
    checked_urls: set[str] = set()

    for a in soup.find_all("a", href=True):
        if len(checked_urls) >= MAX_LINKS_TO_CHECK:
            break
        full_url = urljoin(base_url, a["href"])
        if urlparse(full_url).netloc.lower() == base_domain:
            checked_urls.add(full_url)

    checked = len(checked_urls)
    broken = sum(1 for link in checked_urls if _link_is_broken(link))
    inconclusive = checked >= 3 and broken == checked

    return checked, broken, inconclusive


def _link_is_broken(url: str) -> bool:
    try:
        response = _session.head(url, timeout=LINK_CHECK_TIMEOUT, allow_redirects=True)
        if response.status_code in (405, 501):
            response = _session.get(url, timeout=LINK_CHECK_TIMEOUT, allow_redirects=True, stream=True)
        return response.status_code >= 400
    except requests.RequestException:
        try:
            response = _session.get(url, timeout=LINK_CHECK_TIMEOUT, allow_redirects=True, stream=True)
            return response.status_code >= 400
        except requests.RequestException:
            return True