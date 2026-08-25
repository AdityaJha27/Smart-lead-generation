import logging

logger = logging.getLogger(__name__)

WEIGHTS = {
    "about": 15,
    "email_valid": 20,
    "phone": 15,
    "address": 15,
    "services_or_products": 10,
    "founded": 10,
    "employees": 10,
    "company_linkedin": 10,
    "maps_rating": 10,
}

SOCIAL_ONE_PROFILE_POINTS = 3
SOCIAL_MULTI_PROFILE_POINTS = 5

SCORE_HOT = 70
SCORE_WARM = 40


def score_lead(company: dict) -> dict:
    result = {
        **company,
        "lead_score": 0,
        "priority": None,
        "score_breakdown": {},
        "scoring_explanation": [],
    }

    breakdown = {}
    reasons = []

    if company.get("about"):
        breakdown["about"] = WEIGHTS["about"]
        reasons.append("Has company description")
    if company.get("email_status") == "valid":
        breakdown["email_valid"] = WEIGHTS["email_valid"]
        reasons.append("Email domain has a valid MX record")
    if company.get("phone"):
        breakdown["phone"] = WEIGHTS["phone"]
        reasons.append("Phone number available")
    if company.get("address"):
        breakdown["address"] = WEIGHTS["address"]
        reasons.append("Structured address available")
    if company.get("services") or company.get("products"):
        breakdown["services_or_products"] = WEIGHTS["services_or_products"]
        reasons.append("Services/products listed")
    if company.get("founded"):
        breakdown["founded"] = WEIGHTS["founded"]
        reasons.append("Founding year known")
    if company.get("employees"):
        breakdown["employees"] = WEIGHTS["employees"]
        reasons.append("Employee count known")

    social_links = company.get("social_media") or []
    social_count = len(social_links)
    if social_count >= 2:
        breakdown["social_media"] = SOCIAL_MULTI_PROFILE_POINTS
        reasons.append(f"{social_count} social media profiles found")
    elif social_count == 1:
        breakdown["social_media"] = SOCIAL_ONE_PROFILE_POINTS
        reasons.append("Social media profile found")

    has_company_linkedin = any("linkedin.com/company/" in link.lower() for link in social_links)
    if has_company_linkedin:
        breakdown["company_linkedin"] = WEIGHTS["company_linkedin"]
        reasons.append("Has a verified company LinkedIn page")

    rating = company.get("maps_rating")
    if rating is not None:
        if rating >= 4.5:
            breakdown["maps_rating"] = WEIGHTS["maps_rating"]
            reasons.append(f"Excellent Google rating ({rating})")
        elif rating >= 4.0:
            breakdown["maps_rating"] = round(WEIGHTS["maps_rating"] * 0.6)
            reasons.append(f"Good Google rating ({rating})")
        elif rating >= 3.0:
            breakdown["maps_rating"] = round(WEIGHTS["maps_rating"] * 0.3)
            reasons.append(f"Average Google rating ({rating})")

    score = min(sum(breakdown.values()), 100)
    result["lead_score"] = score
    result["priority"] = _priority_for(score)
    result["score_breakdown"] = breakdown
    result["scoring_explanation"] = reasons

    return result


def score_leads(companies: list[dict]) -> list[dict]:
    return [score_lead(c) for c in companies]


def _priority_for(score: int) -> str:
    if score >= SCORE_HOT:
        return "Hot"
    if score >= SCORE_WARM:
        return "Warm"
    return "Cold"