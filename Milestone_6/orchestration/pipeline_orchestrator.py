from __future__ import annotations
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.home() / "gigavolt-milestone6"
INGESTION = ROOT / "ingestion"
sys.path.insert(0, str(INGESTION))
from telemetry_loader import ingest as ingest_telemetry
from sql_loader import ingest as ingest_sql
from document_loader import ingest_document

LOG_FILE = ROOT / "logs" / "pipeline.log"
RESULT_FILE = ROOT / "results" / "last_pipeline_run.json"
DOCUMENT_EXTENSIONS = {".txt", ".pdf", ".docx", ".html", ".htm", ".xml"}

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def configure_logging():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
    )

def run_one(kind, path):
    if kind == "telemetry":
        return ingest_telemetry(path)
    if kind == "sql":
        return ingest_sql(path)
    if kind == "document":
        return ingest_document(path)
    raise ValueError(f"Unknown pipeline kind: {kind}")

def collect_files():
    work = []
    for path in sorted((ROOT / "incoming" / "telemetry").glob("*.json")):
        work.append(("telemetry", path))
    for path in sorted((ROOT / "incoming" / "sql").glob("*.csv")):
        work.append(("sql", path))
    for path in sorted((ROOT / "incoming" / "documents").iterdir()):
        if path.is_file() and path.suffix.lower() in DOCUMENT_EXTENSIONS:
            work.append(("document", path))
    return work

def main():
    configure_logging()
    started = utc_now()
    logging.info("Milestone 6 pipeline started")
    rows = []
    failures = 0
    for kind, path in collect_files():
        try:
            logging.info("Processing %s: %s", kind, path.name)
            result = run_one(kind, path)
            rows.append({
                "type": kind,
                "file": str(path.relative_to(ROOT)),
                "status": result.get("status"),
                "result": result,
            })
            logging.info("Completed %s: %s -> %s", kind, path.name, result.get("status"))
        except Exception as exc:
            failures += 1
            rows.append({
                "type": kind,
                "file": str(path.relative_to(ROOT)),
                "status": "FAILED",
                "error": str(exc),
            })
            logging.exception("Failed %s: %s", kind, path.name)
    summary = {
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "files_seen": len(rows),
        "failures": failures,
        "results": rows,
    }
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text(json.dumps(summary, indent=2, default=str) + "\n")
    logging.info("Pipeline finished: files=%s failures=%s", len(rows), failures)
    print("\nPIPELINE SUMMARY")
    print(json.dumps(summary, indent=2, default=str))
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
