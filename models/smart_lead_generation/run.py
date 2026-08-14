import logging

from . import exporter, master_store
from .company_extractor import extract_companies
from .contact_discovery import discover_contacts
from .search_engine import search_companies
from .user_input import collect_user_input

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# stops urllib3 from printing our serpapi key in its request-url warnings
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

    exporter.export(with_contacts, "company_data")
    master_store.upsert(with_contacts)

    ok = sum(1 for r in with_contacts if r["about"])
    contacts_found = sum(1 for r in with_contacts if r["email"] or r["phone"])
    print(f"\nDone: {ok}/{len(with_contacts)} fully enriched, {contacts_found}/{len(with_contacts)} with contact info.")
    print("Snapshot -> output/company_data_<timestamp>.json/.csv")
    print("Master   -> output/master_leads.json/.csv")


if __name__ == "__main__":
    main()