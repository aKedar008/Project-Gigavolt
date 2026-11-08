from pymongo import MongoClient
import re


class MongoRetriever:
    def __init__(self, uri="mongodb://localhost:27017"):
        self.client = MongoClient(uri)
        self.collection = self.client["gigavolt"]["telemetry"]

    def extract_equipment_id(self, question):
        match = re.search(r"\bSN-[A-Za-z0-9-]+\b", question, re.IGNORECASE)
        return match.group(0) if match else None

    def extract_model(self, question):
        q = question.lower()

        if "x-7000" in q or "x7000" in q:
            return "Gigavolt Megapack X-7000"

        if "c-1200" in q or "c1200" in q:
            return "C-1200"

        if "g-3500" in q or "g3500" in q:
            return "PowerStation G-3500"

        return None

    def retrieve(self, question, limit=5):
        query = {}

        equipment_id = self.extract_equipment_id(question)
        model = self.extract_model(question)

        if equipment_id:
            query["equipment_id"] = equipment_id

        if model:
            query["model"] = model

        q = question.lower()

        if any(word in q for word in ["failure", "fault", "error", "problem"]):
            query["fault_code"] = {"$ne": None}

        if any(word in q for word in [
            "high temperature",
            "high-temperature",
            "over-temperature",
            "over temperature",
            "hot"
        ]):
            query["telemetry.temperature_c"] = {"$gte": 50}

        docs = list(
            self.collection.find(query)
            .sort("timestamp", -1)
            .limit(limit)
        )

        evidence = []

        for doc in docs:
            telemetry = doc.get("telemetry", {})

            content = (
                f"Equipment {doc.get('equipment_id')} "
                f"({doc.get('model')}) recorded status {doc.get('status')} "
                f"at {doc.get('timestamp')}. "
                f"Fault code: {doc.get('fault_code')}. "
                f"Severity: {doc.get('severity')}. "
                f"Temperature: {telemetry.get('temperature_c')} C. "
                f"Voltage: {telemetry.get('voltage_v')} V. "
                f"Current: {telemetry.get('current_a')} A. "
                f"SOC: {telemetry.get('soc_percent')}%. "
                f"Notes: {doc.get('notes')}"
            )

            evidence.append({
                "source_type": "mongodb",
                "source_id": doc.get("log_id"),
                "source_name": "telemetry",
                "timestamp": str(doc.get("timestamp")),
                "content": content,
                "score": 1.0
            })

        return evidence


if __name__ == "__main__":
    retriever = MongoRetriever()

    question = (
        "What are common failure modes for X-7000 "
        "in high-temperature environments?"
    )

    results = retriever.retrieve(question)

    for result in results:
        print("\n", result)
