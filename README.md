# Smart Lead Generation

An automated pipeline that discovers companies by location and industry, enriches them with business details, audits their website health, discovers decision makers, scores and prioritizes them, and exports a clean, CRM-ready dataset — all without manual research.

## Overview

Given a location, an industry, and a target number of leads, the pipeline runs through nine stages and produces a fully enriched, scored, and deduplicated dataset — including company details, contact info, website health, decision-maker info, and lead priority.

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
   │ 5. Enrichment    │  Services/products, website health audit
   │                  │  (SEO/mobile/speed/broken links), decision maker
   │                  │  discovery (name/title/LinkedIn via live search)
   └─────────────────┘
            │
            ▼
   ┌─────────────────┐
   │ 6. Verification  │  Validates each email's domain via MX record lookup
   └─────────────────┘
            │
            ▼
   ┌─────────────────┐
   │ 7. Scoring       │  Data-completeness lead score + sales-opportunity
   │                  │  priority (website health + Google rating)
   └─────────────────┘
            │
            ▼
   ┌─────────────────┐
   │ 8. Quality Flags │  Flags incomplete/possible-duplicate leads —
   │                  │  never deletes real data
   └─────────────────┘
            │
            ▼
   ┌─────────────────┐
   │ 9. CRM Export    │  Curated, human-readable CSV for sales use
   └─────────────────┘
            │
            ▼
     output/*.json, output/*.csv, output/crm_export.csv
```

## Features

- **Broad discovery** — 6 query variations, paginated until the requested lead count is reached or genuinely exhausted (no hidden cap on lead count).
- **Directory & listicle filtering** — skips aggregator sites (JustDial, IndiaMART, 99acres, etc.) and "Top 10..." style articles, keeping only real company pages.
- **Structured-data-first extraction** — prefers JSON-LD/schema.org data over guessed text, for about, founded year, employee count, and company name.
- **Quality filters** — rejects junk emails, junk phone numbers, and untrustworthy addresses (only structured data is used, never free-text guessing).
- **Country-aware phone validation** — uses Google's `phonenumbers` library, works for any country, not just India.
- **Structured-list-only enrichment** — services/products are only taken from genuine `<ul>`/`<ol>` HTML lists after a matching heading.
- **Website health audit** — checks HTTPS, SEO structure, mobile-responsiveness, page load speed, outdated tech stack, content freshness, image accessibility, and broken links; runs concurrently across leads for speed.
- **Decision maker discovery** — finds the likely CEO/Founder/Director name, title, and LinkedIn profile using live web search; an LLM only formats what the search actually returned, never guesses from its own knowledge.
- **Google Maps rating lookup** — additive, optional signal for companies with a Maps listing; not required, not fabricated when absent.
- **Email domain verification** — every discovered email's domain is checked for a working MX record before being marked `valid`.
- **Dual scoring system** — a data-completeness lead score (how much do we know) and a separate opportunity-priority score (how much does this lead need our services, e.g. no website = highest priority).
- **Quality flagging, not deletion** — incomplete or possibly-duplicate leads are flagged for review, never silently dropped; missing data is never treated as a fake company.
- **CRM-ready export** — a separate, curated CSV with human-readable summaries (e.g. combined website-issue text) alongside the full technical dataset.
- **Deduplicated master store** — every run merges into one running dataset keyed by domain; re-running never creates duplicates.
- **Safe by default** — bot-protected sites, SSL errors, DNS failures, and rate-limited APIs are handled gracefully with retries; API keys are never printed to logs.

## Tech Stack

Python 3.10+ · `requests` · `beautifulsoup4` · `python-dotenv` · `phonenumbers` · `dnspython` · `google-genai` · [SerpApi](https://serpapi.com/)

## Setup

```bash
git clone https://github.com/AdityaJha27/Smart-lead-generation.git
cd Smart-lead-generation

python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS/Linux

pip install -r requirements.txt

cp .env.example .env
```

Open `.env` and add:

```
SERPAPI_KEY=your_key_here
GEMINI_API_KEY=your_key_here
```

`GEMINI_API_KEY` is optional — if not set, decision maker discovery is skipped gracefully; every other module still works.

## Usage

```bash
python -m models.smart_lead_generation.run
```

You'll be prompted for **location**, **industry**, and **number of leads** — no fixed upper limit.

## Output

| File | Description |
|---|---|
| `output/company_data_<timestamp>.json` / `.csv` | Snapshot of that specific run |
| `output/master_leads.json` / `.csv` | Full, running, deduplicated dataset across all runs |
| `output/crm_export.csv` | Curated, sales-team-facing view of the current master dataset |

Example record (full schema, in `master_leads.json`):

```json
{
  "company_name": "Example Corp",
  "website": "https://example.com",
  "location": "Mumbai, India",
  "industry": "Real Estate",
  "about": "...",
  "founded": "2015",
  "employees": "50",
  "social_media": ["https://linkedin.com/company/example"],
  "email": "contact@example.com",
  "phone": "+91 98765 43210",
  "address": "123 Main St, Mumbai, MH, 400001, India",
  "services": ["Residential Services"],
  "products": [],
  "email_status": "valid",
  "has_website": true,
  "website_audit": {
    "uses_https": true,
    "reachable": true,
    "load_time_seconds": 1.2,
    "mobile_responsive": true,
    "issues": [],
    "issue_count": 0
  },
  "decision_maker_name": "Jane Doe",
  "decision_maker_title": "Founder & CEO",
  "decision_maker_linkedin": "https://linkedin.com/in/janedoe",
  "maps_rating": 4.5,
  "lead_score": 85,
  "priority": "Hot",
  "score_breakdown": {"about": 15, "email_valid": 20},
  "opportunity_priority": "Low",
  "opportunity_reason": "Website has no significant issues detected",
  "quality_flag": "ok",
  "created_at": "2026-08-25T10:00:00+00:00",
  "last_updated": "2026-08-25T10:00:00+00:00"
}
```

Fields are left empty when data genuinely can't be found — never guessed or fabricated.

## Project Structure

```
AI_ENGINE/
├── models/
│   └── smart_lead_generation/
│       ├── user_input.py               # Module 1: CLI input collection
│       ├── search_engine.py            # Module 2: company discovery via SerpApi
│       ├── company_extractor.py        # Module 3: about, founded, employees, socials, name
│       ├── contact_discovery.py        # Module 4: email, phone, address extraction
│       ├── lead_enrichment.py          # Module 5: services/products extraction
│       ├── website_audit.py            # Module 5: website health audit
│       ├── decision_maker_discovery.py # Module 5: decision maker discovery (LLM + search)
│       ├── email_verification.py       # Module 6: MX-record email verification
│       ├── lead_scoring.py             # Module 7: data-completeness lead scoring
│       ├── opportunity_scoring.py      # Module 7: sales-opportunity priority
│       ├── google_maps_rating.py       # Module 7: optional Maps rating lookup
│       ├── lead_quality.py             # Module 8: quality/duplicate flagging
│       ├── crm_export.py               # Module 9: curated CRM-ready CSV export
│       ├── master_store.py             # Deduplicated master dataset
│       ├── exporter.py                 # JSON/CSV export
│       ├── config.py                   # Env vars and shared settings
│       └── run.py                      # Pipeline entry point
├── output/                             # Generated at runtime, not tracked in git
├── .env.example
├── .gitignore
└── requirements.txt
```

## Design Notes

- Address extraction only trusts structured data (JSON-LD/microdata) — a free-text label fallback was tried and dropped after it picked up testimonials and cookie-popup text instead of real addresses.
- Services/products extraction only trusts genuine `<ul>`/`<ol>` lists after a matching heading — a looser `<div>`/`<p>` fallback was tried and dropped after it occasionally grabbed unrelated UI text instead of actual list items.
- Phone numbers are validated with Google's `phonenumbers` library rather than a hand-written regex, so results aren't limited to one country and clearly invalid numbers (e.g. a date range mistaken for digits) are rejected.
- Website link-checking falls back from HEAD to GET requests (some servers reject HEAD even though the page works fine), and reports "could not verify" rather than "broken" when a check is genuinely inconclusive — avoiding false claims about a healthy site.
- Decision maker discovery uses an LLM only to extract/format facts from live search results, never to answer from its own training knowledge — if search results don't mention a name, the LLM is instructed to return null, not guess.
- Lead scoring and opportunity scoring are two separate, intentionally distinct signals: one measures how much verified data exists for a lead, the other measures how much the lead needs the services being offered (e.g. no website scores highest on opportunity, regardless of data completeness).
- Quality flagging never deletes a record — missing data is not treated as a fake company; records are flagged (`incomplete`, `possible_duplicate`) for human review instead.
- Email verification checks MX records only, not a full SMTP handshake — most mail servers block or rate-limit SMTP verification, and it risks getting the sending IP flagged.
- No artificial cap on lead count — the pipeline genuinely tries to find as many real companies as exist for the given location/industry.

## Roadmap

- [x] Module 1 — User Input Collection
- [x] Module 2 — Business Search Engine
- [x] Module 3 — Company Data Extraction
- [x] Module 4 — Contact Discovery
- [x] Module 5 — Lead Data Enrichment (services/products, website audit, decision maker discovery)
- [x] Module 6 — Email Verification
- [x] Module 7 — AI Lead Scoring (data-completeness + opportunity scoring)
- [x] Module 8 — Deduplication & Quality Filtering
- [x] Module 9 — Output Formatting & CRM Export

All 9 modules complete.