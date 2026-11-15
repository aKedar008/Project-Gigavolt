from __future__ import annotations
import json
import os
from pathlib import Path
import mysql.connector
from dotenv import load_dotenv
from pymongo import MongoClient

M5_ENV = Path.home() / "gigavolt-milestone5" / ".env"
RESULT = Path.home() / "gigavolt-milestone6" / "results" / "index_optimization.json"

def mariadb_indexes():
    load_dotenv(M5_ENV)
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        database=os.getenv("MYSQL_DATABASE"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
    )
    database = os.getenv("MYSQL_DATABASE")
    cur = conn.cursor()
    requested = [
        ("service_history", "idx_service_equipment_date", "CREATE INDEX idx_service_equipment_date ON service_history (equipment_id, service_date)"),
        ("warranty_claims", "idx_claim_equipment_date", "CREATE INDEX idx_claim_equipment_date ON warranty_claims (equipment_id, claim_date)"),
    ]
    results = []
    for table, index_name, ddl in requested:
        cur.execute(
            """
            SELECT COUNT(*) FROM information_schema.statistics
            WHERE table_schema = %s AND table_name = %s AND index_name = %s
            """,
            (database, table, index_name),
        )
        if cur.fetchone()[0] > 0:
            results.append({"table": table, "index": index_name, "status": "EXISTING"})
            continue
        try:
            cur.execute(ddl)
            conn.commit()
            results.append({"table": table, "index": index_name, "status": "CREATED"})
        except Exception as exc:
            conn.rollback()
            results.append({"table": table, "index": index_name, "status": "SKIPPED", "reason": str(exc)})
    cur.close()
    conn.close()
    return results

def mongodb_indexes():
    client = MongoClient("mongodb://localhost:27017")
    collection = client["gigavolt"]["telemetry"]
    requested = [
        [("log_id", 1)],
        [("equipment_id", 1), ("timestamp", -1)],
        [("model", 1), ("timestamp", -1)],
        [("fault_code", 1)],
        [("telemetry.temperature_c", 1)],
    ]
    results = []
    for keys in requested:
        try:
            name = collection.create_index(keys)
            results.append({"keys": keys, "index": name, "status": "READY"})
        except Exception as exc:
            results.append({"keys": keys, "status": "SKIPPED", "reason": str(exc)})
    client.close()
    return results

def main():
    result = {"mariadb": mariadb_indexes(), "mongodb": mongodb_indexes()}
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    main()
