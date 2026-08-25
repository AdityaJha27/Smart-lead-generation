import json as _json
import logging
import re
import time

import requests
from google import genai
from requests.adapters import HTTPAdapter, Retry

from . import config

logger = logging.getLogger(__name__)

_MODEL_NAME = "gemini-3.6-flash"
_MAX_LLM_RETRIES = 3

_gemini_client = None
if config.GEMINI_API_KEY:
    _gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not set - decision maker discovery will be skipped for all leads.")

_session = requests.Session()
_session.mount(
    "https://",
    HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503])),
)

LINKEDIN_PROFILE_PATTERN = re.compile(r"https?://[\w.]*linkedin\.com/in/[^\s\"'?&]+", re.IGNORECASE)


def discover_decision_maker(company: dict) -> dict:
    result = {**company, "decision_maker_name": None, "decision_maker_title": None, "decision_maker_linkedin": None}

    if not _gemini_client:
        return result

    company_name = company.get("company_name")
    website = company.get("website", "")
    location = company.get("location", "")

    if not company_name or not website:
        return result

    domain = _domain_of(website)
    query = f'"{company_name}" {location} CEO OR Founder OR "Managing Director" OR Director'
    snippets = _search(query, domain_hint=domain)

    if not snippets:
        return result

    extracted = _extract_with_llm(company_name, snippets)
    if not extracted or not extracted.get("name"):
        return result

    result["decision_maker_name"] = extracted.get("name")
    result["decision_maker_title"] = extracted.get("title")

    linkedin_query = f'{extracted.get("name")} {company_name} LinkedIn'
    result["decision_maker_linkedin"] = _find_linkedin_url(linkedin_query)

    return result


def discover_decision_makers(companies: list[dict]) -> list[dict]:
    return [discover_decision_maker(c) for c in companies]


def _search(query: str, domain_hint: str) -> list[str]:
    params = {"q": query, "api_key": config.SERPAPI_KEY, "engine": "google"}
    try:
        response = _session.get(config.SERPAPI_URL, params=params, timeout=config.REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException:
        logger.error("SerpApi request failed for decision-maker search")
        return []

    results = response.json().get("organic_results", [])
    snippets = []
    for r in results[:5]:
        snippet = r.get("snippet", "")
        if snippet:
            snippets.append(snippet)
    return snippets[:5]


def _extract_with_llm(company_name: str, snippets: list[str]) -> dict | None:
    if not _gemini_client:
        return None

    prompt = (
        "You are extracting facts from search-result snippets only. Do not use any "
        "outside knowledge. If the snippets do not clearly name a decision maker "
        f'(CEO, Founder, Managing Director, or Director) for the company "{company_name}", '
        'respond with exactly: {"name": null, "title": null}\n\n'
        "Otherwise respond with strict JSON only, no other text:\n"
        '{"name": "<full name>", "title": "<their title>"}\n\n'
        "Search result snippets:\n" + "\n---\n".join(snippets)
    )

    for attempt in range(_MAX_LLM_RETRIES):
        try:
            response = _gemini_client.models.generate_content(
                model=_MODEL_NAME,
                contents=prompt,
            )
            text = re.sub(r"^```json\s*|\s*```$", "", response.text.strip())
            return _json.loads(text)
        except Exception as e:
            if "429" in str(e) and attempt < _MAX_LLM_RETRIES - 1:
                wait = 2 ** attempt
                logger.warning("Rate limited on %s, retrying in %ds", company_name, wait)
                time.sleep(wait)
                continue
            logger.warning("LLM extraction failed for %s: %s", company_name, e)
            return None
    return None


def _find_linkedin_url(query: str) -> str | None:
    params = {"q": query, "api_key": config.SERPAPI_KEY, "engine": "google"}
    try:
        response = _session.get(config.SERPAPI_URL, params=params, timeout=config.REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException:
        return None

    for r in response.json().get("organic_results", []):
        match = LINKEDIN_PROFILE_PATTERN.search(r.get("link", ""))
        if match:
            return match.group(0)
    return None


def _domain_of(url: str) -> str:
    domain = re.sub(r"^https?://", "", url, flags=re.IGNORECASE).split("/")[0].lower()
    return domain[4:] if domain.startswith("www.") else domain