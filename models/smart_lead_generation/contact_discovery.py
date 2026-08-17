import json as _json
import logging
import re
import urllib.parse as _urlparse

import phonenumbers
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

JUNK_PHONE_LITERALS = {"undefined", "null", "none", "n/a", "na", ""}

COUNTRY_NAME_TO_ISO = {
    "india": "IN", "usa": "US", "united states": "US",
    "uk": "GB", "united kingdom": "GB",
    "uae": "AE", "united arab emirates": "AE", "dubai": "AE",
    "canada": "CA", "australia": "AU", "singapore": "SG",
    "germany": "DE", "france": "FR", "china": "CN", "japan": "JP",
}

_session = requests.Session()
_session.headers.update(config.HEADERS)
_session.mount(
    "https://",
    HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503])),
)


def discover_contact(company: dict) -> dict:
    result = {**company, "email": None, "phone": None, "address": None, "contact_page_used": None}

    website = company.get("website", "")
    default_region = _region_from_location(company.get("location", ""))
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    page_used = website

    html = _fetch(website)
    if html:
        email = _extract_email(html, website)
        phone = _extract_phone(html, default_region)
        address = _extract_address(html)

    if not email:
        for path in CONTACT_PATHS:
            candidate_html = _fetch(website.rstrip("/") + path)
            if not candidate_html:
                continue
            page_used = website.rstrip("/") + path
            email = email or _extract_email(candidate_html, website)
            phone = phone or _extract_phone(candidate_html, default_region)
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


def _extract_phone(html: str, default_region: str | None) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    tel_link = soup.find("a", href=re.compile(r"^tel:"))
    if tel_link:
        raw = _urlparse.unquote(tel_link["href"].split(":", 1)[1].strip())
        validated = _validate_phone(raw, default_region)
        if validated:
            return validated

    text = soup.get_text(" ", strip=True)
    for match in PHONE_PATTERN.findall(text):
        validated = _validate_phone(match, default_region)
        if validated:
            return validated
    return None


def _region_from_location(location: str) -> str | None:
    if not location:
        return None
    tail = location.split(",")[-1].strip().lower()
    return COUNTRY_NAME_TO_ISO.get(tail)


def _validate_phone(candidate: str, default_region: str | None) -> str | None:
    if candidate.lower().strip() in JUNK_PHONE_LITERALS:
        return None
    try:
        parsed = phonenumbers.parse(candidate, default_region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)


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


def _domain_of(url: str) -> str:
    domain = re.sub(r"^https?://", "", url, flags=re.IGNORECASE).split("/")[0].lower()
    return domain[4:] if domain.startswith("www.") else domain