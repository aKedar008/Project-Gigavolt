import os
import re
import sys
import time
import json

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

RETRIEVAL_DIR = os.path.join(PROJECT_ROOT, "retrieval")

if RETRIEVAL_DIR not in sys.path:
    sys.path.insert(0, RETRIEVAL_DIR)

from hybrid_retriever import HybridRetriever

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


class GigavoltRAG:

    def __init__(self):

        print("Initializing Gigavolt RAG system...")

        self.retriever = HybridRetriever()

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is missing from .env"
            )

        self.client = OpenAI(api_key=api_key)

        self.model = os.getenv(
            "OPENAI_MODEL",
            "gpt-6-luna"
        )

        print("RAG system ready.")
        print("LLM model:", self.model)

    def select_evidence(self, evidence):

        selected = []

        counts = {
            "sql": 0,
            "mongodb": 0,
            "vector": 0
        }

        limits = {
            "sql": 3,
            "mongodb": 3,
            "vector": 4
        }

        seen = set()

        for item in evidence:

            source_type = item.get(
                "source_type",
                "unknown"
            )

            if source_type not in counts:
                continue

            if counts[source_type] >= limits[source_type]:
                continue

            dedup_key = (
                source_type,
                item.get("source_id")
            )

            if dedup_key in seen:
                continue

            seen.add(dedup_key)

            selected.append(item)

            counts[source_type] += 1

        return selected

    def build_context(self, evidence):

        sources = []
        provenance = {}

        for index, item in enumerate(evidence, 1):

            citation = f"S{index}"

            source_type = item.get(
                "source_type",
                "unknown"
            )

            source_id = item.get(
                "source_id",
                "unknown"
            )

            source_name = item.get(
                "source_name",
                "unknown"
            )

            content = item.get(
                "content",
                ""
            )

            timestamp = item.get(
                "timestamp"
            )

            provenance[citation] = {
                "source_type": source_type,
                "source_id": source_id,
                "source_name": source_name,
                "timestamp": timestamp,
                "chunk_index": item.get(
                    "chunk_index"
                )
            }

            source_block = (
                f"[{citation}]\n"
                f"Source type: {source_type}\n"
                f"Source ID: {source_id}\n"
                f"Source name: {source_name}\n"
            )

            if timestamp:
                source_block += (
                    f"Timestamp: {timestamp}\n"
                )

            if (
                "synthetic_demo"
                in content
            ):
                source_block += (
                    "DATA WARNING: This source contains "
                    "synthetic demonstration data.\n"
                )

            source_block += (
                f"Evidence:\n{content}\n"
            )

            sources.append(source_block)

        return "\n\n".join(sources), provenance

    def build_prompt(
        self,
        question,
        context
    ):

        return f"""
You are the Gigavolt technical support RAG assistant.

Answer the user's question using ONLY the evidence supplied below.

STRICT RULES:

1. Every factual claim must have one or more citations such as [S1][S2]. Never use citation ranges such as [S1-S4] or [S1–S4].
2. Never invent citation numbers.
3. Never use outside knowledge.
4. If the evidence is insufficient, explicitly say so.
5. Distinguish telemetry observations from engineering documentation.
6. Do not claim correlation proves causation.
7. Records marked synthetic_demo are demonstration data created for this academic prototype. Explicitly describe them as synthetic/demo records if referenced.
8. Professor telemetry records and technical documents must not be described as synthetic unless the evidence says so.
9. Keep the response concise and technical. Prefer 2-4 short paragraphs or bullets and answer within about 180 words.
10.Do not include a separate bibliography. Cite evidence inline.

USER QUESTION:
{question}

RETRIEVED EVIDENCE:

{context}

ANSWER:
""".strip()

    def validate_citations(
        self,
        answer,
        provenance
    ):

        cited = set(
            re.findall(
                r"\[S(\d+)\]",
                answer
            )
        )

        allowed = set(
            key[1:]
            for key in provenance.keys()
        )

        invalid = sorted(
            cited - allowed,
            key=int
        )

        valid = sorted(
            cited & allowed,
            key=int
        )

        return {
            "valid_citations": [
                f"S{x}" for x in valid
            ],
            "invalid_citations": [
                f"S{x}" for x in invalid
            ],
            "citation_validation_passed":
                len(invalid) == 0
                and len(valid) > 0
        }

    def answer(self, question):

        total_start = time.perf_counter()

        retrieval_start = time.perf_counter()

        retrieval_result = (
            self.retriever.retrieve(question)
        )

        retrieval_ms = round(
            (
                time.perf_counter()
                - retrieval_start
            ) * 1000,
            2
        )

        selected = self.select_evidence(
            retrieval_result["evidence"]
        )

        context, provenance = (
            self.build_context(selected)
        )

        prompt = self.build_prompt(
            question,
            context
        )

        llm_start = time.perf_counter()

        response = self.client.responses.create(
                model=self.model,
                input=prompt,
                max_output_tokens=500
            )        

        llm_ms = round(
            (
                time.perf_counter()
                - llm_start
            ) * 1000,
            2
        )

        answer = response.output_text.strip()

        validation = self.validate_citations(
            answer,
            provenance
        )

        total_ms = round(
            (
                time.perf_counter()
                - total_start
            ) * 1000,
            2
        )

        return {
            "question": question,
            "answer": answer,
            "sources_used":
                retrieval_result[
                    "sources_used"
                ],
            "retrieval_timings":
                retrieval_result[
                    "timings"
                ],
            "retrieval_total_ms":
                retrieval_ms,
            "llm_ms": llm_ms,
            "total_ms": total_ms,
            "provenance": provenance,
            "citation_validation":
                validation
        }


def print_result(result):

    print("\n" + "=" * 80)

    print("QUESTION:")
    print(result["question"])

    print("\nANSWER:")
    print(result["answer"])

    print("\nSOURCES USED:")
    print(
        ", ".join(
            result["sources_used"]
        )
    )

    print("\nPROVENANCE:")

    for citation, info in (
        result["provenance"].items()
    ):

        print(
            f"[{citation}] "
            f"{info['source_type']} | "
            f"{info['source_id']} | "
            f"{info['source_name']}"
        )

    print("\nCITATION VALIDATION:")
    print(
        json.dumps(
            result[
                "citation_validation"
            ],
            indent=2
        )
    )

    print("\nLATENCY:")
    print(
        "Retrieval:",
        result["retrieval_total_ms"],
        "ms"
    )

    print(
        "LLM:",
        result["llm_ms"],
        "ms"
    )

    print(
        "Total:",
        result["total_ms"],
        "ms"
    )


if __name__ == "__main__":

    rag = GigavoltRAG()

    questions = [
        (
            "What are common failure modes for "
            "X-7000 batteries in high-temperature "
            "environments?"
        ),
        (
            "Show me service history for equipment "
            "SN-4829 and related warranty claims."
        ),
        (
            "What maintenance actions are recommended "
            "after an X-7000 inverter fault?"
        )
    ]

    results = []

    for question in questions:

        result = rag.answer(question)

        results.append(result)

        print_result(result)

    output_file = os.path.join(
        PROJECT_ROOT,
        "results",
        "rag_test_results.json"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            results,
            f,
            indent=2,
            default=str
        )

    print(
        "\nSaved results to:",
        output_file
    )
