import logging
import re

logger = logging.getLogger(__name__)

COMPANY_SUFFIX_PATTERN = re.compile(
    r"\b(pvt\.?|private|ltd\.?|limited|llp|inc\.?|corp\.?|corporation|group|realty|realtors?)\b",
    re.IGNORECASE,
)


def _normalize_name(name: str) -> str:
    if not name:
        return ""
    cleaned = COMPANY_SUFFIX_PATTERN.sub("", name.lower())
    cleaned = re.sub(r"[^a-z0-9 ]", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def flag_leads(companies: list[dict]) -> list[dict]:
    seen_name_location: dict[tuple, str] = {}
    results = []

    for company in companies:
        result = {**company, "quality_flag": None}

        name = company.get("company_name")
        website = company.get("website")

        if not name or not website:
            result["quality_flag"] = "invalid"
            results.append(result)
            continue

        norm_key = (_normalize_name(name), (company.get("location") or "").lower().strip())
        existing_domain = seen_name_location.get(norm_key)

        has_signal = bool(company.get("about") or company.get("email") or company.get("phone"))

        if existing_domain and existing_domain != website:
            result["quality_flag"] = "possible_duplicate"
        elif has_signal:
            result["quality_flag"] = "ok"
        else:
            result["quality_flag"] = "incomplete"

        seen_name_location.setdefault(norm_key, website)
        results.append(result)

    return results