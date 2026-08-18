import logging

from . import exporter, master_store
from .company_extractor import extract_companies
from .contact_discovery import discover_contacts
from .email_verification import verify_emails
from .lead_enrichment import enrich_leads
from .lead_quality import flag_leads
from .lead_scoring import score_leads
from .search_engine import search_companies
from .user_input import collect_user_input

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)


def main() -> None:
    params = collect_user_input()

    print(f"\nSearching {params['industry']} companies in {params['location']}...")
    leads = search_companies(params["location"], params["industry"], params["num_leads"])
    print(f"Found {len(leads)} candidates. Extracting details...\n")

    enriched = extract_companies(leads)

    print("\nDiscovering contact info...")
    with_contacts = discover_contacts(enriched)

    print("\nEnriching services/products...")
    fully_enriched = enrich_leads(with_contacts)

    print("\nVerifying emails...")
    fully_enriched = verify_emails(fully_enriched)

    print("\nScoring leads...")
    fully_enriched = score_leads(fully_enriched)

    print("\nFlagging quality issues...")
    fully_enriched = flag_leads(fully_enriched)

    exporter.export(fully_enriched, "company_data")
    master_store.upsert(fully_enriched)

    ok = sum(1 for r in fully_enriched if r["about"])
    contacts_found = sum(1 for r in fully_enriched if r["email"] or r["phone"])
    services_found = sum(1 for r in fully_enriched if r["services"] or r["products"])
    valid_emails = sum(1 for r in fully_enriched if r["email_status"] == "valid")
    hot_leads = sum(1 for r in fully_enriched if r["priority"] == "Hot")
    ok_quality = sum(1 for r in fully_enriched if r["quality_flag"] == "ok")
    print(
        f"\nDone: {ok}/{len(fully_enriched)} fully enriched, "
        f"{contacts_found}/{len(fully_enriched)} with contact info, "
        f"{services_found}/{len(fully_enriched)} with services/products, "
        f"{valid_emails}/{len(fully_enriched)} with verified emails, "
        f"{hot_leads}/{len(fully_enriched)} Hot leads, "
        f"{ok_quality}/{len(fully_enriched)} passed quality check."
    )
    print("Snapshot -> output/company_data_<timestamp>.json/.csv")
    print("Master   -> output/master_leads.json/.csv")


if __name__ == "__main__":
    main()