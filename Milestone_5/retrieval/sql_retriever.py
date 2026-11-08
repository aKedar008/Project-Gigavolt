import os
import re
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


class SQLRetriever:

    def __init__(self):
        self.config = {
            "host": os.getenv("MYSQL_HOST"),
            "port": int(os.getenv("MYSQL_PORT", 3306)),
            "database": os.getenv("MYSQL_DATABASE"),
            "user": os.getenv("MYSQL_USER"),
            "password": os.getenv("MYSQL_PASSWORD")
        }

    def extract_equipment_id(self, question):
        match = re.search(
            r"\bSN-[A-Za-z0-9-]+\b",
            question,
            re.IGNORECASE
        )
        return match.group(0) if match else None

    def retrieve(self, question, limit=10):

        equipment_id = self.extract_equipment_id(question)

        if not equipment_id:
            return []

        connection = mysql.connector.connect(**self.config)
        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT
            e.equipment_id,
            e.model,
            e.warranty_status,
            e.warranty_expiration,
            e.telemetry_record_count,

            s.service_id,
            s.service_date,
            s.service_type,
            s.problem_code,
            s.resolution,
            s.record_origin AS service_origin,

            w.claim_id,
            w.claim_date,
            w.claim_type,
            w.status AS claim_status,
            w.claim_amount,
            w.failure_code,
            w.record_origin AS claim_origin

        FROM equipment e

        LEFT JOIN service_history s
            ON e.equipment_id = s.equipment_id

        LEFT JOIN warranty_claims w
            ON e.equipment_id = w.equipment_id

        WHERE e.equipment_id = %s

        ORDER BY s.service_date DESC
        LIMIT %s
        """

        cursor.execute(
            query,
            (equipment_id, limit)
        )

        rows = cursor.fetchall()

        evidence = []

        for row in rows:

            content = (
                f"Equipment {row['equipment_id']} "
                f"is model {row['model']}. "
                f"Warranty status: {row['warranty_status']}. "
                f"Warranty expiration: {row['warranty_expiration']}. "
                f"Telemetry records: {row['telemetry_record_count']}. "
            )

            if row["service_id"]:
                content += (
                    f"Service record {row['service_id']} on "
                    f"{row['service_date']}: "
                    f"{row['service_type']}. "
                    f"Problem code: {row['problem_code']}. "
                    f"Resolution: {row['resolution']}. "
                    f"Record origin: {row['service_origin']}. "
                )

            if row["claim_id"]:
                content += (
                    f"Warranty claim {row['claim_id']} dated "
                    f"{row['claim_date']}. "
                    f"Claim type: {row['claim_type']}. "
                    f"Status: {row['claim_status']}. "
                    f"Amount: {row['claim_amount']}. "
                    f"Failure code: {row['failure_code']}. "
                    f"Record origin: {row['claim_origin']}."
                )

            source_id = (
                row["service_id"]
                or row["claim_id"]
                or row["equipment_id"]
            )

            evidence.append({
                "source_type": "sql",
                "source_id": source_id,
                "source_name": "gigavolt_m5",
                "equipment_id": row["equipment_id"],
                "content": content,
                "score": 1.0
            })

        cursor.close()
        connection.close()

        return evidence


if __name__ == "__main__":

    retriever = SQLRetriever()

    question = (
        "Show me service history for equipment "
        "SN-4829 and related warranty claims"
    )

    results = retriever.retrieve(question)

    for result in results:
        print("\n", result)
