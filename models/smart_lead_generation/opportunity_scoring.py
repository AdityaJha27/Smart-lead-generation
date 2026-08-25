import logging

logger = logging.getLogger(__name__)

HIGH_ISSUE_THRESHOLD = 5
MEDIUM_ISSUE_THRESHOLD = 2


def score_opportunity(company: dict) -> dict:
    result = {**company, "opportunity_priority": None, "opportunity_reason": None}

    if not company.get("has_website"):
        result["opportunity_priority"] = "Highest"
        result["opportunity_reason"] = "No website found - strongest candidate for web development services"
        return result

    audit = company.get("website_audit") or {}
    if not audit.get("reachable"):
        result["opportunity_priority"] = "Highest"
        result["opportunity_reason"] = "Website exists but is unreachable - likely broken or abandoned"
        return result

    issue_count = audit.get("issue_count", 0)
    issues = audit.get("issues", [])

    if issue_count >= HIGH_ISSUE_THRESHOLD:
        priority = "High"
    elif issue_count >= MEDIUM_ISSUE_THRESHOLD:
        priority = "Medium"
    else:
        priority = "Low"

    result["opportunity_priority"] = priority
    result["opportunity_reason"] = ", ".join(issues) if issues else "Website has no significant issues detected"
    return result


def score_opportunities(companies: list[dict]) -> list[dict]:
    return [score_opportunity(c) for c in companies]