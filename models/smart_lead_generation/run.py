import logging

from . import exporter, master_store
from .company_extractor import extract_companies
from .contact_discovery import discover_contacts
from .crm_export import export_crm_csv
from .decision_maker_discovery import discover_decision_makers
from .email_verification import verify_emails
from .google_maps_rating import lookup_ratings
from .lead_enrichment import enrich_leads
from .lead_quality import flag_leads
from .lead_scoring import score_leads
from .opportunity_scoring import score_opportunities
from .search_engine import search_companies
from .user_input import collect_user_input
from .website_audit import audit_websites

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

    print("\nAuditing websites...")
    fully_enriched = audit_websites(fully_enriched)

    print("\nDiscovering decision makers...")
    fully_enriched = discover_decision_makers(fully_enriched)

    print("\nLooking up Google ratings...")
    fully_enriched = lookup_ratings(fully_enriched)

    print("\nScoring leads...")
    fully_enriched = score_leads(fully_enriched)

    print("\nScoring opportunity...")
    fully_enriched = score_opportunities(fully_enriched)

    print("\nFlagging quality issues...")
    fully_enriched = flag_leads(fully_enriched)

    exporter.export(fully_enriched, "company_data")
    master_records = master_store.upsert(fully_enriched)
    export_crm_csv(master_records)

    ok = sum(1 for r in fully_enriched if r["about"])
    contacts_found = sum(1 for r in fully_enriched if r["email"] or r["phone"])
    services_found = sum(1 for r in fully_enriched if r["services"] or r["products"])
    valid_emails = sum(1 for r in fully_enriched if r["email_status"] == "valid")
    hot_leads = sum(1 for r in fully_enriched if r["priority"] == "Hot")
    ok_quality = sum(1 for r in fully_enriched if r["quality_flag"] == "ok")
    highest_opportunity = sum(1 for r in fully_enriched if r["opportunity_priority"] == "Highest")
    decision_makers_found = sum(1 for r in fully_enriched if r["decision_maker_name"])
    ratings_found = sum(1 for r in fully_enriched if r["maps_rating"] is not None)
    print(
        f"\nDone: {ok}/{len(fully_enriched)} fully enriched, "
        f"{contacts_found}/{len(fully_enriched)} with contact info, "
        f"{services_found}/{len(fully_enriched)} with services/products, "
        f"{valid_emails}/{len(fully_enriched)} with verified emails, "
        f"{hot_leads}/{len(fully_enriched)} Hot leads, "
        f"{ok_quality}/{len(fully_enriched)} passed quality check, "
        f"{highest_opportunity}/{len(fully_enriched)} Highest opportunity, "
        f"{decision_makers_found}/{len(fully_enriched)} decision makers found, "
        f"{ratings_found}/{len(fully_enriched)} with Google ratings."
    )
    print("Snapshot -> output/company_data_<timestamp>.json/.csv")
    print("Master   -> output/master_leads.json/.csv")
    print("CRM      -> output/crm_export.csv")


if __name__ == "__main__":
    main()