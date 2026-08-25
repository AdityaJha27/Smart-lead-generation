import logging
import re

import dns.exception
import dns.resolver

logger = logging.getLogger(__name__)

EMAIL_SYNTAX_PATTERN = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

_mx_cache: dict[str, bool] = {}


def verify_email(company: dict) -> dict:
    result = {**company, "email_status": None}
    email = company.get("email")

    if not email:
        result["email_status"] = "no_email"
        return result

    if not EMAIL_SYNTAX_PATTERN.match(email):
        result["email_status"] = "invalid_syntax"
        return result

    domain = email.split("@", 1)[1].lower()
    result["email_status"] = "valid" if _has_mx_record(domain) else "no_mx_record"
    return result


def verify_emails(companies: list[dict]) -> list[dict]:
    return [verify_email(c) for c in companies]


def _has_mx_record(domain: str) -> bool:
    if domain in _mx_cache:
        return _mx_cache[domain]

    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=5)
        result = len(answers) > 0
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers, dns.exception.Timeout):
        result = False
    except Exception:
        logger.warning("Unexpected error checking MX record for %s", domain)
        result = False

    _mx_cache[domain] = result
    return result