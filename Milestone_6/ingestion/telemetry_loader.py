from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime

from pymongo import MongoClient, UpdateOne

ROOT = Path.home() / "gigavolt-milestone6"
ORCHESTRATION = ROOT / "orchestration"

sys.path.insert(0, str(ORCHESTRATION))

from manifest import check_file, mark_processed, mark_failed


MONGO_URI = "mongodb://localhost:27017"
DATABASE = "gigavolt"
COLLECTION = "telemetry"


REQUIRED_FIELDS = {
    "log_id",
    "equipment_id",
    "timestamp"
}


def validate_record(record):
    errors = []

    missing = [
        field
        for field in REQUIRED_FIELDS
        if not record.get(field)
    ]

    if missing:
        errors.append(
            "missing required fields: " + ", ".join(missing)
        )

    timestamp = record.get("timestamp")

    if timestamp:
        try:
            datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            )
        except ValueError:
            errors.append("invalid timestamp")

    telemetry = record.get("telemetry")

    if telemetry is not None and not isinstance(telemetry, dict):
        errors.append("telemetry must be an object")

    flagged = record.get("flagged_components")

    if flagged is not None and not isinstance(flagged, list):
        errors.append("flagged_components must be an array")

    return errors


def load_records(path):
    text = path.read_text().strip()

    if not text:
        raise ValueError("input file is empty")

    # Accept either a normal JSON object/array
    # or newline-delimited JSON.
    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return [parsed]

        if isinstance(parsed, list):
            return parsed

        raise ValueError("JSON must contain object or array")

    except json.JSONDecodeError:
        records = []

        for number, line in enumerate(
            text.splitlines(),
            start=1
        ):
            line = line.strip()

            if not line:
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON on line {number}: {exc}"
                )

        return records


def ingest(path):
    path = path.resolve()

    state = check_file(path)

    print(
        f"{state['status']}: "
        f"{state['path']}"
    )

    if state["status"] == "UNCHANGED":
        print("Skipping unchanged file.")
        return {
            "status": "SKIPPED",
            "loaded": 0
        }

    try:
        records = load_records(path)

        valid_records = []

        for index, record in enumerate(records, start=1):
            errors = validate_record(record)

            if errors:
                raise ValueError(
                    f"record {index}: " + "; ".join(errors)
                )

            valid_records.append(record)

        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000
        )

        client.admin.command("ping")

        collection = client[DATABASE][COLLECTION]

        operations = [
            UpdateOne(
                {"log_id": record["log_id"]},
                {"$set": record},
                upsert=True
            )
            for record in valid_records
        ]

        if operations:
            result = collection.bulk_write(
                operations,
                ordered=False
            )

            print(
                "MongoDB result:",
                f"matched={result.matched_count}",
                f"modified={result.modified_count}",
                f"upserted={result.upserted_count}"
            )

        mark_processed(
            path,
            stage="mongodb-telemetry"
        )

        client.close()

        return {
            "status": "SUCCESS",
            "loaded": len(valid_records)
        }

    except Exception as exc:
        mark_failed(
            path,
            error=str(exc),
            stage="mongodb-telemetry"
        )

        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "file",
        type=Path
    )

    args = parser.parse_args()

    result = ingest(args.file)

    print(json.dumps(result, indent=2))
