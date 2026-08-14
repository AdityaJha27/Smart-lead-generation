import csv
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"  # AI_ENGINE/output


def export(records: list[dict], base_filename: str) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = OUTPUT_DIR / f"{base_filename}_{timestamp}.json"
    csv_path = OUTPUT_DIR / f"{base_filename}_{timestamp}.csv"

    json_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_csv(records, csv_path)

    logger.info("Exported %d records to %s and %s", len(records), json_path.name, csv_path.name)
    return json_path, csv_path


def _write_csv(records: list[dict], path: Path) -> None:
    if not records:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = list(records[0].keys())
    for record in records:
        for key in record:
            if key not in fieldnames:
                fieldnames.append(key)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({k: _flatten(v) for k, v in record.items()})


def _flatten(value):
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return value if value is not None else ""