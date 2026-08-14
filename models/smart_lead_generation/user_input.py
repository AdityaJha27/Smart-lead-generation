SANITY_CEILING = 1000  # catches accidental typos, not a real business limit


def get_location() -> str:
    while True:
        value = input("Enter target location (e.g. Mumbai, India): ").strip()
        if value:
            return value
        print("  Location cannot be empty.")


def get_industry() -> str:
    while True:
        value = input("Enter target industry (e.g. Real Estate): ").strip()
        if value:
            return value
        print("  Industry cannot be empty.")


def get_num_leads() -> int:
    while True:
        raw = input("How many leads do you want (as many as available if not sure): ").strip()
        if not raw.isdigit() or int(raw) <= 0:
            print("  Enter a whole number greater than 0.")
            continue

        value = int(raw)
        if value > SANITY_CEILING:
            print(f"  {value} is unusually high and may exhaust the SerpApi quota in one run.")
            confirm = input(f"  Proceed with {value} anyway? (y/n): ").strip().lower()
            if confirm != "y":
                continue

        return value


def collect_user_input() -> dict:
    print("=== Smart Lead Generation ===")
    return {
        "location": get_location(),
        "industry": get_industry(),
        "num_leads": get_num_leads(),
    }