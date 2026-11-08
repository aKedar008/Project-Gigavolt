from mongo_retriever import MongoRetriever
from vector_retriever import VectorRetriever
from sql_retriever import SQLRetriever
import re
import time


class HybridRetriever:

    def __init__(self):
        print("Initializing hybrid retrieval system...")

        self.mongo = MongoRetriever()
        self.vector = VectorRetriever()
        self.sql = SQLRetriever()

        print("Hybrid retrieval system ready.")

    def detect_sources(self, question):
        q = question.lower()

        # Always use vector retrieval for technical context
        sources = {"vector"}

        # Detect equipment serial number
        has_serial = bool(
            re.search(
                r"\bSN-[A-Za-z0-9-]+\b",
                question,
                re.IGNORECASE
            )
        )

        # Equipment-specific questions should use SQL + MongoDB
        if has_serial:
            sources.add("sql")
            sources.add("mongo")

        # Structured database keywords
        if any(word in q for word in [
            "service",
            "warranty",
            "claim",
            "equipment",
            "serial"
        ]):
            sources.add("sql")

        # Telemetry / fault keywords
        if any(word in q for word in [
            "fault",
            "failure",
            "temperature",
            "telemetry",
            "voltage",
            "current",
            "battery",
            "error",
            "overheat",
            "thermal"
        ]):
            sources.add("mongo")

        return sources

    def retrieve(self, question):
        selected_sources = self.detect_sources(question)

        print("\nSelected sources:")
        for source in sorted(selected_sources):
            print(" -", source)

        evidence = []
        timings = {}

        if "sql" in selected_sources:
            start = time.perf_counter()

            sql_results = self.sql.retrieve(question)

            timings["sql_ms"] = round(
                (time.perf_counter() - start) * 1000,
                2
            )

            evidence.extend(sql_results)

        if "mongo" in selected_sources:
            start = time.perf_counter()

            mongo_results = self.mongo.retrieve(question)

            timings["mongo_ms"] = round(
                (time.perf_counter() - start) * 1000,
                2
            )

            evidence.extend(mongo_results)

        if "vector" in selected_sources:
            start = time.perf_counter()

            vector_results = self.vector.retrieve(question)

            timings["vector_ms"] = round(
                (time.perf_counter() - start) * 1000,
                2
            )

            evidence.extend(vector_results)

        return {
            "question": question,
            "sources_used": sorted(selected_sources),
            "evidence": evidence,
            "timings": timings
        }


if __name__ == "__main__":

    retriever = HybridRetriever()

    questions = [
        "What are common failure modes for X-7000 batteries in high-temperature environments?",

        "Show me service history for equipment SN-4829 and related warranty claims",

        "What maintenance actions are recommended after an X-7000 inverter fault?"
    ]

    for question in questions:

        print("\n" + "=" * 80)
        print("QUESTION:")
        print(question)

        result = retriever.retrieve(question)

        print("\nTIMINGS:")
        print(result["timings"])

        print("\nEVIDENCE:")

        for i, item in enumerate(result["evidence"], 1):

            print("\n" + "-" * 60)
            print("Evidence", i)
            print("Type:", item["source_type"])
            print("Source ID:", item["source_id"])
            print("Source:", item["source_name"])
            print("Content:")
            print(item["content"][:700])
