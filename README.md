# Smart Lead Generation

An automated pipeline that discovers companies by location and industry, enriches them with business details, and finds their contact information — producing a clean, deduplicated leads dataset ready for outreach.

## Overview

Given a location, an industry, and a target number of leads, the pipeline runs through four stages and produces a structured dataset of companies with their website, about section, founding year, employee count, social media links, email, phone, and address.

```
Location + Industry + Lead Count
            │
            ▼
   ┌─────────────────┐
   │  1. Search       │  Finds candidate companies via SerpApi
   └─────────────────┘
            │
            ▼
   ┌─────────────────┐
   │  2. Extract      │  Scrapes each site for company details
   └─────────────────┘
            │
            ▼
   ┌─────────────────┐
   │  3. Contacts     │  Finds email, phone, and address
   └─────────────────┘
            │
            ▼
   ┌─────────────────┐
   │  4. Master Store │  Deduplicates and merges into one dataset
   └─────────────────┘
            │
            ▼
     output/*.json, output/*.csv
```

## Features

- **Broad discovery** — searches multiple query variations and pages until the requested number of leads is found or genuinely exhausted.
- **Directory & listicle filtering** — skips aggregator sites (JustDial, IndiaMART, LinkedIn, etc.) and "Top 10..." style article results, keeping only real company pages.
- **Structured-data-first extraction** — prefers JSON-LD/schema.org data over guessed text, since it's far more reliable.
- **Quality filters** — rejects junk emails (noreply@, placeholder domains), junk phone numbers (000000, 123456789), and false-positive addresses.
- **Contact page fallback** — if the homepage has no contact info, tries common contact page paths (`/contact`, `/contact-us`, etc.) once.
- **Deduplicated master store** — every run merges into a single running dataset keyed by domain, so re-running never creates duplicates; newer non-empty values overwrite stale ones.
- **Safe by default** — bot-protected sites (Cloudflare, Akamai) are skipped rather than force-opened; API keys are never printed to logs.

## Tech Stack

- Python 3.10+
- `requests` — HTTP fetching with retry logic
- `beautifulsoup4` — HTML parsing
- `python-dotenv` — environment variable management
- [SerpApi](https://serpapi.com/) — Google search results

## Setup

**1. Clone the repository**

```bash
git clone https://github.com/AdityaJha27/Smart-lead-generation.git
cd Smart-lead-generation
```

**2. Create and activate a virtual environment**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Set up environment variables**

```bash
cp .env.example .env
```

Open `.env` and add your SerpApi key:

```
SERPAPI_KEY=your_key_here
```

## Usage

Run the pipeline from the project root:

```bash
python -m models.smart_lead_generation.run
```

You'll be prompted for:

- **Location** — e.g. `Mumbai, India`
- **Industry** — e.g. `Real Estate`
- **Number of leads** — how many companies to find

The pipeline will search, extract, and print a summary once complete.

## Output

Every run produces two things inside `output/`:

| File | Description |
|---|---|
| `company_data_<timestamp>.json` / `.csv` | Snapshot of that specific run |
| `master_leads.json` / `.csv` | Running, deduplicated dataset across all runs |

Each record contains:

```json
{
  "company_name": "Example Corp",
  "website": "https://example.com",
  "about": "...",
  "founded": "2015",
  "employees": "50",
  "social_media": ["https://linkedin.com/company/example"],
  "email": "contact@example.com",
  "phone": "+91 98765 43210",
  "address": "123 Main St, Mumbai, MH, 400001, India",
  "contact_page_used": "https://example.com/contact",
  "created_at": "2026-08-14T10:00:00+00:00",
  "last_updated": "2026-08-14T10:00:00+00:00"
}
```

## Project Structure

```
AI_ENGINE/
├── models/
│   └── smart_lead_generation/
│       ├── company_extractor.py     # Scrapes about, founded, employees, socials
│       ├── config.py                # Env vars and shared settings
│       ├── contact_discovery.py     # Email, phone, address extraction
│       ├── exporter.py              # JSON/CSV export
│       ├── master_store.py          # Deduplicated master dataset
│       ├── run.py                   # Pipeline entry point
│       ├── search_engine.py         # Company discovery via SerpApi
│       └── user_input.py            # CLI input collection
├── output/                          # Generated at runtime, not tracked in git
├── .env.example
├── .gitignore
└── requirements.txt
```

## Design Notes

- Contact extraction only trusts structured data (JSON-LD/microdata) for addresses — a free-text label fallback was tried and dropped because it kept picking up testimonials and cookie-popup text instead of real addresses. Fewer filled rows with zero garbage is the right tradeoff here.
- JS-rendered sites and bot-protected pages are intentionally skipped rather than force-opened with a headless browser — that belongs in a separate, dedicated enrichment pass.
- Lead count has no artificial low ceiling; the pipeline searches as many query variations and pages as needed (up to a high safety ceiling) to genuinely try to hit the requested number.