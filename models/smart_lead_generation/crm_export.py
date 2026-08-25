import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"

CRM_FIELDS = [
    "company_name",
    "website",
    "location",
    "industry",
    "about",
    "decision_maker_name",
    "decision_maker_title",
    "decision_maker_linkedin",
    "email",
    "email_status",
    "phone",
    "address",
    "services",
    "products",
    "website_status",
    "website_issues_summary",
    "opportunity_priority",
    "lead_score",
    "priority",
    "maps_rating",
    "quality_flag",
    "created_at",
    "last_updated",
]


def build_crm_records(companies: list[dict]) -> list[dict]:
    return [_build_crm_record(c) for c in companies]


def _build_crm_record(company: dict) -> dict:
    audit = company.get("website_audit") or {}
    issues = audit.get("issues") or []

    record = {field: company.get(field, "") for field in CRM_FIELDS}
    record["website_status"] = "No website" if not company.get("has_website") else (
        "Unreachable" if not audit.get("reachable") else "Reachable"
    )
    record["website_issues_summary"] = "; ".join(issues) if issues else "No significant issues"
    return record


def export_crm_csv(companies: list[dict]) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    csv_path = OUTPUT_DIR / "crm_export.csv"

    records = build_crm_records(companies)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CRM_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow({k: _flatten(record.get(k)) for k in CRM_FIELDS})

    logger.info("Exported %d CRM-ready records to %s", len(records), csv_path.name)
    return csv_path


def _flatten(value):
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return value if value is not None else ""