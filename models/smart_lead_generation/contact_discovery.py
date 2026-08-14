import json as _json
import logging
import re
import urllib.parse as _urlparse

import requests
import urllib3
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

from . import config

logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[\s.\-]?)?(?:\(?\d{2,4}\)?[\s.\-]?)?\d{3,4}[\s.\-]?\d{3,4}\b"
)

CONTACT_PATHS = ("/contact", "/contact-us", "/contactus", "/en/contact")

JUNK_EMAIL_DOMAINS = {
    "sentry.io", "wixpress.com", "example.com", "test.com", "domain.com",
    "mailchimp.com", "sendgrid.net", "amazonses.com", "w3.org", "schema.org",
    "google.com", "googleapis.com", "cloudflare.com", "wordpress.com",
    "godaddy.com", "wix.com", "shopify.com", "sentry.wixpress.com",
}
JUNK_EMAIL_LOCAL_PARTS = {
    "noreply", "no-reply", "donotreply", "do-not-reply", "mailer", "bounce",
    "postmaster", "webmaster", "example", "test", "dummy", "placeholder",
    "unsubscribe", "notification", "wordpress", "woocommerce", "shopify",
}
JUNK_EMAIL_PATTERNS = (
    re.compile(r"^[a-f0-9]{16,}@"),
    re.compile(r"^\d{6,}@"),
)

JUNK_PHONE_PATTERNS = (
    re.compile(r"^0+$"),
    re.compile(r"^1234567?890?$"),
)

JUNK_PHONE_LITERALS = {"undefined", "null", "none", "n/a", "na", ""}

_session = requests.Session()
_session.headers.update(config.HEADERS)
_session.mount(
    "https://",
    HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503])),
)


def discover_contact(company: dict) -> dict:
    result = {**company, "email": None, "phone": None, "address": None, "contact_page_used": None}

    website = company.get("website", "")
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    page_used = website

    html = _fetch(website)
    if html:
        email = _extract_email(html, website)
        phone = _extract_phone(html)
        address = _extract_address(html)

    if not email:
        for path in CONTACT_PATHS:
            candidate_html = _fetch(website.rstrip("/") + path)
            if not candidate_html:
                continue
            page_used = website.rstrip("/") + path
            email = email or _extract_email(candidate_html, website)
            phone = phone or _extract_phone(candidate_html)
            address = address or _extract_address(candidate_html)
            if email:
                break

    result["email"] = email
    result["phone"] = phone
    result["address"] = address
    result["contact_page_used"] = page_used if page_used != website and (email or phone) else None
    return result


def discover_contacts(companies: list[dict]) -> list[dict]:
    return [discover_contact(c) for c in companies]


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


def _extract_email(html: str, website: str) -> str | None:
    candidates = set(EMAIL_PATTERN.findall(html))
    clean = [e for e in candidates if not _is_junk_email(e)]
    if not clean:
        return None
    site_domain = _domain_of(website)
    own_domain = [e for e in clean if e.lower().endswith("@" + site_domain)]
    return own_domain[0] if own_domain else sorted(clean)[0]


def _extract_phone(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    tel_link = soup.find("a", href=re.compile(r"^tel:"))
    if tel_link:
        number = _urlparse.unquote(tel_link["href"].split(":", 1)[1].strip())
        if number.lower() not in JUNK_PHONE_LITERALS and _looks_like_phone(number):
            return number

    text = soup.get_text(" ", strip=True)
    for match in PHONE_PATTERN.findall(text):
        if _looks_like_phone(match):
            return match.strip()
    return None


def _looks_like_phone(candidate: str) -> bool:
    digits = re.sub(r"\D", "", candidate)
    if not (7 <= len(digits) <= 13):
        return False
    if _is_junk_phone(digits):
        return False
    # avoids matching things like "2026-2027" as a phone number
    if len(digits) == 8:
        y1, y2 = int(digits[:4]), int(digits[4:])
        if 1990 <= y1 <= 2035 and 1990 <= y2 <= 2035 and 0 <= (y2 - y1) <= 1:
            return False
    return True


def _extract_address(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    return _address_from_jsonld(soup) or _address_from_microdata(soup)


def _address_from_jsonld(soup: BeautifulSoup) -> str | None:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = _json.loads(tag.string or "")
        except (ValueError, TypeError):
            continue
        for entry in (data if isinstance(data, list) else [data]):
            if not isinstance(entry, dict) or entry.get("@type") not in ("Organization", "Corporation", "LocalBusiness"):
                continue
            addr = entry.get("address")
            if isinstance(addr, dict):
                parts = [
                    addr.get("streetAddress"), addr.get("addressLocality"),
                    addr.get("addressRegion"), addr.get("postalCode"), addr.get("addressCountry"),
                ]
                cleaned = ", ".join(p for p in parts if p)
                if cleaned:
                    return cleaned
            elif isinstance(addr, str) and addr.strip():
                return addr.strip()
    return None


def _address_from_microdata(soup: BeautifulSoup) -> str | None:
    container = soup.find(attrs={"itemprop": "address"}) or soup.find(attrs={"itemtype": re.compile("PostalAddress", re.I)})
    if not container:
        return None
    text = container.get_text(" ", strip=True)
    return text if len(text) >= 15 else None


def _is_junk_email(email: str) -> bool:
    email = email.lower().strip()
    local, _, domain = email.partition("@")
    if domain in JUNK_EMAIL_DOMAINS or any(domain.endswith("." + d) for d in JUNK_EMAIL_DOMAINS):
        return True
    if any(junk in local for junk in JUNK_EMAIL_LOCAL_PARTS):
        return True
    return any(p.search(email) for p in JUNK_EMAIL_PATTERNS)


def _is_junk_phone(number: str) -> bool:
    digits_only = re.sub(r"\D", "", number)
    return any(p.match(digits_only) for p in JUNK_PHONE_PATTERNS)


def _domain_of(url: str) -> str:
    domain = re.sub(r"^https?://", "", url, flags=re.IGNORECASE).split("/")[0].lower()
    return domain[4:] if domain.startswith("www.") else domain