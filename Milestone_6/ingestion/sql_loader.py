from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

ROOT = Path.home() / "gigavolt-milestone6"
M5_ENV = Path.home() / "gigavolt-milestone5" / ".env"

sys.path.insert(0, str(ROOT / "orchestration"))

from manifest import check_file, mark_processed, mark_failed


REQUIRED_COLUMNS = {
    "equipment_id",
    "model",
    "warranty_expiration",
    "warranty_status",
    "telemetry_record_count",
    "metadata_source"
}


def get_connection():
    load_dotenv(M5_ENV)

    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        database=os.getenv("MYSQL_DATABASE"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
    )


def load_csv(path: Path):
    with path.open(newline="") as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise ValueError("CSV has no header")

        missing = REQUIRED_COLUMNS - set(reader.fieldnames)

        if missing:
            raise ValueError(
                "missing columns: " + ", ".join(sorted(missing))
            )

        rows = list(reader)

    if not rows:
        raise ValueError("CSV contains no data rows")

    return rows


def validate_row(row, row_number):
    if not row["equipment_id"].strip():
        raise ValueError(
            f"row {row_number}: equipment_id is required"
        )

    try:
        count = int(row["telemetry_record_count"])
    except ValueError:
        raise ValueError(
            f"row {row_number}: telemetry_record_count must be integer"
        )

    if count < 0:
        raise ValueError(
            f"row {row_number}: telemetry_record_count cannot be negative"
        )


def ingest(path: Path):
    path = path.resolve()

    state = check_file(path)

    print(f"{state['status']}: {state['path']}")

    if state["status"] == "UNCHANGED":
        print("Skipping unchanged file.")
        return {
            "status": "SKIPPED",
            "loaded": 0
        }

    conn = None

    try:
        rows = load_csv(path)

        for number, row in enumerate(rows, start=2):
            validate_row(row, number)

        conn = get_connection()
        cursor = conn.cursor()

        sql = """
        INSERT INTO equipment (
            equipment_id,
            model,
            warranty_expiration,
            warranty_status,
            telemetry_record_count,
            metadata_source
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            model = VALUES(model),
            warranty_expiration = VALUES(warranty_expiration),
            warranty_status = VALUES(warranty_status),
            telemetry_record_count = VALUES(telemetry_record_count),
            metadata_source = VALUES(metadata_source)
        """

        for row in rows:
            cursor.execute(
                sql,
                (
                    row["equipment_id"].strip(),
                    row["model"].strip(),
                    row["warranty_expiration"].strip() or None,
                    row["warranty_status"].strip(),
                    int(row["telemetry_record_count"]),
                    row["metadata_source"].strip()
                )
            )

        conn.commit()

        cursor.close()
        conn.close()
        conn = None

        mark_processed(
            path,
            stage="mariadb-equipment"
        )

        return {
            "status": "SUCCESS",
            "loaded": len(rows)
        }

    except Exception as exc:
        if conn is not None:
            conn.rollback()
            conn.close()

        mark_failed(
            path,
            error=str(exc),
            stage="mariadb-equipment"
        )

        raise


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path)

    args = parser.parse_args()

    result = ingest(args.file)

    print(json.dumps(result, indent=2))
