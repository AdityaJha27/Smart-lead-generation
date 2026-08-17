# Smart Lead Generation

An automated pipeline that discovers companies by location and industry, enriches them with business details, finds their contact information, and verifies their emails — producing a clean, deduplicated leads dataset ready for outreach.

## Overview

Given a location, an industry, and a target number of leads, the pipeline runs through six stages and produces a structured dataset of companies with their website, about section, founding year, employee count, social media links, services/products, email (verified), phone, and address.

```
Location + Industry + Lead Count
            │
            ▼
   ┌─────────────────┐
   │ 1. User Input    │  Validated CLI prompts (location, industry, count)
   └─────────────────┘
            │
            ▼
   ┌─────────────────┐
   │ 2. Search        │  Finds candidate companies via SerpApi;
   │                  │  filters out directories & listicle articles
   └─────────────────┘
            │
            ▼
   ┌─────────────────┐
   │ 3. Extract       │  Scrapes each site for about, founded, employees,
   │                  │  socials, and company name (JSON-LD preferred)
   └─────────────────┘
            │
            ▼
   ┌─────────────────┐
   │ 4. Contacts      │  Finds email, phone, and address
   └─────────────────┘
            │
            ▼
   ┌─────────────────┐
   │ 5. Enrichment    │  Finds services/products from structured page
   │                  │  headings (<ul>/<ol> lists only)
   └─────────────────┘
            │
            ▼
   ┌─────────────────┐
   │ 6. Verification  │  Validates each email's domain via MX record lookup
   └─────────────────┘
            │
            ▼
   ┌─────────────────┐
   │ Master Store     │  Deduplicates and merges into one dataset
   └─────────────────┘
            │
            ▼
     output/*.json, output/*.csv
```

## Features

- **Broad discovery** — 6 query variations, paginated until the requested lead count is reached or genuinely exhausted (no hidden cap on lead count).
- **Directory & listicle filtering** — skips aggregator sites (JustDial, IndiaMART, 99acres, etc.) and "Top 10..." style articles, keeping only real company pages.
- **Structured-data-first extraction** — prefers JSON-LD/schema.org data over guessed text, for about, founded year, employee count, and company name.
- **Quality filters** — rejects junk emails (noreply@, placeholders), junk phone numbers (JS placeholders, date-like false positives), and untrustworthy addresses (only structured data is used, never free-text guessing).
- **Country-aware phone validation** — uses Google's `phonenumbers` library to validate against real country-specific numbering rules, not a generic digit-count heuristic. Works for any country, not just India.
- **Structured-list-only enrichment** — services/products are only taken from genuine `<ul>`/`<ol>` HTML lists after a matching heading, never from loose paragraph/div text, to avoid capturing unrelated page content.
- **Email domain verification** — every discovered email's domain is checked for a working MX record before being marked `valid`, catching typo domains and non-existent mail servers.
- **Contact page fallback** — if the homepage has no contact info, tries `/contact`, `/contact-us`, etc. once.
- **Deduplicated master store** — every run merges into one running dataset keyed by domain; re-running never creates duplicates.
- **Safe by default** — bot-protected sites (Cloudflare, Akamai), SSL errors, and DNS failures are skipped and logged, never crash the pipeline. API keys are never printed to logs.

## Tech Stack

Python 3.10+ · `requests` · `beautifulsoup4` · `python-dotenv` · `phonenumbers` · `dnspython` · [SerpApi](https://serpapi.com/)

## Setup

```bash
git clone https://github.com/AdityaJha27/Smart-lead-generation.git
cd Smart-lead-generation

python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS/Linux

pip install -r requirements.txt

cp .env.example .env           # then add SERPAPI_KEY=your_key_here
```

## Usage

```bash
python -m models.smart_lead_generation.run
```

You'll be prompted for **location**, **industry**, and **number of leads** — no fixed upper limit.

## Output

| File | Description |
|---|---|
| `output/company_data_<timestamp>.json` / `.csv` | Snapshot of that specific run |
| `output/master_leads.json` / `.csv` | Running, deduplicated dataset across all runs |

```json
{
  "company_name": "Example Corp",
  "website": "https://example.com",
  "location": "Mumbai, India",
  "about": "...",
  "founded": "2015",
  "employees": "50",
  "social_media": ["https://linkedin.com/company/example"],
  "email": "contact@example.com",
  "phone": "+91 98765 43210",
  "address": "123 Main St, Mumbai, MH, 400001, India",
  "contact_page_used": "https://example.com/contact",
  "services": ["Residential Services", "Commercial Services"],
  "products": [],
  "email_status": "valid",
  "created_at": "2026-08-14T10:00:00+00:00",
  "last_updated": "2026-08-14T10:00:00+00:00"
}
```

Fields are left empty when data genuinely can't be found — never guessed or fabricated. `email_status` is one of `valid`, `no_email`, `invalid_syntax`, or `no_mx_record`.

## Project Structure

```
AI_ENGINE/
├── models/
│   └── smart_lead_generation/
│       ├── user_input.py          # Module 1: CLI input collection
│       ├── search_engine.py       # Module 2: company discovery via SerpApi
│       ├── company_extractor.py   # Module 3: about, founded, employees, socials, name
│       ├── contact_discovery.py   # Module 4: email, phone, address extraction
│       ├── lead_enrichment.py     # Module 5: services/products extraction
│       ├── email_verification.py # Module 6: MX-record email verification
│       ├── master_store.py        # Deduplicated master dataset
│       ├── exporter.py            # JSON/CSV export
│       ├── config.py              # Env vars and shared settings
│       └── run.py                 # Pipeline entry point
├── output/                        # Generated at runtime, not tracked in git
├── .env.example
├── .gitignore
└── requirements.txt
```

## Design Notes

- Address extraction only trusts structured data (JSON-LD/microdata) — a free-text label fallback was tried and dropped after it picked up testimonials and cookie-popup text instead of real addresses.
- Services/products extraction only trusts genuine `<ul>`/`<ol>` lists after a matching heading — a looser `<div>`/`<p>` fallback was tried and dropped after it occasionally grabbed unrelated UI text instead of actual list items.
- Phone numbers are validated with Google's `phonenumbers` library rather than a hand-written regex, so results aren't limited to one country and clearly invalid numbers (e.g. a date range mistaken for digits) are rejected.
- Email verification checks MX records only, not a full SMTP handshake — most mail servers block or rate-limit SMTP verification attempts, and it risks getting the sending IP flagged. MX-record checking is the practical ceiling without a paid verification service.
- Bot-protected/JS-rendered sites are skipped, not force-opened with a headless browser — that belongs in a later, dedicated enrichment pass.
- No artificial cap on lead count — the pipeline genuinely tries to find as many real companies as exist for the given location/industry.

## Roadmap

- [x] Module 1 — User Input Collection
- [x] Module 2 — Business Search Engine
- [x] Module 3 — Company Data Extraction
- [x] Module 4 — Contact Discovery
- [x] Module 5 — Lead Data Enrichment (services/products)
- [x] Module 6 — Email Verification
- [ ] Module 7 — AI Lead Scoring
- [ ] Module 8 — Deduplication & Quality Filtering
- [ ] Module 9 — Output Formatting & CRM Export