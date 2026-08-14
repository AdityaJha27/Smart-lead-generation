import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from . import exporter

logger = logging.getLogger(__name__)

MASTER_DIR = Path(__file__).resolve().parents[2] / "output"
MASTER_JSON = MASTER_DIR / "master_leads.json"
MASTER_CSV = MASTER_DIR / "master_leads.csv"


def _domain_key(website: str) -> str:
    if not website:
        return ""
    netloc = urlparse(website).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def _load() -> dict[str, dict]:
    if not MASTER_JSON.exists():
        return {}
    raw = json.loads(MASTER_JSON.read_text(encoding="utf-8"))
    return {_domain_key(r.get("website", "")): r for r in raw}


def upsert(records: list[dict]) -> list[dict]:
    master = _load()
    now = datetime.now(timezone.utc).isoformat()

    for record in records:
        key = _domain_key(record.get("website", ""))
        if not key:
            continue

        if key in master:
            existing = master[key]
            for field, value in record.items():
                if value not in (None, "", []):
                    existing[field] = value
            existing["last_updated"] = now
        else:
            record = {**record, "created_at": now, "last_updated": now}
            master[key] = record

    all_records = list(master.values())
    _save(all_records)
    logger.info("Master store updated: %d unique leads total", len(all_records))
    return all_records


def _save(records: list[dict]) -> None:
    MASTER_DIR.mkdir(exist_ok=True)
    MASTER_JSON.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    exporter._write_csv(records, MASTER_CSV)