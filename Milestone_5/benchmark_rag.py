import os
import sys
import csv
import json
import statistics
from datetime import datetime, UTC

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

RAG_DIR = os.path.join(PROJECT_ROOT, "rag")

if RAG_DIR not in sys.path:
    sys.path.insert(0, RAG_DIR)

from rag_pipeline import GigavoltRAG


QUESTIONS = [
    "What are common failure modes for X-7000 batteries in high-temperature environments?",
    "Show me service history for equipment SN-4829 and related warranty claims.",
    "What maintenance actions are recommended after an X-7000 inverter fault?"
]

RUNS_PER_QUERY = 5


def percentile(values, percentile_value):
    values = sorted(values)

    if not values:
        return None

    position = (len(values) - 1) * percentile_value

    lower = int(position)
    upper = min(lower + 1, len(values) - 1)

    weight = position - lower

    return (
        values[lower] * (1 - weight)
        + values[upper] * weight
    )


def calculate_stats(values):
    return {
        "count": len(values),
        "min_ms": round(min(values), 2),
        "max_ms": round(max(values), 2),
        "mean_ms": round(statistics.mean(values), 2),
        "p50_ms": round(percentile(values, 0.50), 2),
        "p95_ms": round(percentile(values, 0.95), 2),
        "p99_ms": round(percentile(values, 0.99), 2)
    }


def main():

    print("Initializing benchmark...")
    rag = GigavoltRAG()

    rows = []

    total_latencies = []
    retrieval_latencies = []
    llm_latencies = []

    successful_citations = 0
    total_runs = 0

    for question_index, question in enumerate(QUESTIONS, 1):

        print("\n" + "=" * 80)
        print(f"QUESTION {question_index}")
        print(question)

        for run_number in range(1, RUNS_PER_QUERY + 1):

            print(
                f"\nRun {run_number}/{RUNS_PER_QUERY}"
            )

            try:

                result = rag.answer(question)

                validation = result[
                    "citation_validation"
                ]

                citation_passed = validation[
                    "citation_validation_passed"
                ]

                if citation_passed:
                    successful_citations += 1

                total_runs += 1

                retrieval_ms = result[
                    "retrieval_total_ms"
                ]

                llm_ms = result[
                    "llm_ms"
                ]

                total_ms = result[
                    "total_ms"
                ]

                retrieval_latencies.append(
                    retrieval_ms
                )

                llm_latencies.append(
                    llm_ms
                )

                total_latencies.append(
                    total_ms
                )

                rows.append({
                    "question_id": question_index,
                    "run": run_number,
                    "question": question,
                    "sources_used":
                        ",".join(
                            result["sources_used"]
                        ),
                    "retrieval_ms":
                        retrieval_ms,
                    "llm_ms":
                        llm_ms,
                    "total_ms":
                        total_ms,
                    "citation_passed":
                        citation_passed,
                    "answer":
                        result["answer"]
                })

                print(
                    f"Retrieval: {retrieval_ms} ms | "
                    f"LLM: {llm_ms} ms | "
                    f"Total: {total_ms} ms | "
                    f"Citations: {citation_passed}"
                )

            except Exception as exc:

                total_runs += 1

                print(
                    "ERROR:",
                    str(exc)
                )

                rows.append({
                    "question_id": question_index,
                    "run": run_number,
                    "question": question,
                    "sources_used": "",
                    "retrieval_ms": "",
                    "llm_ms": "",
                    "total_ms": "",
                    "citation_passed": False,
                    "answer": f"ERROR: {exc}"
                })

    results_dir = os.path.join(
        PROJECT_ROOT,
        "results"
    )

    os.makedirs(
        results_dir,
        exist_ok=True
    )

    csv_path = os.path.join(
        results_dir,
        "rag_benchmark.csv"
    )

    with open(
        csv_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "question_id",
                "run",
                "question",
                "sources_used",
                "retrieval_ms",
                "llm_ms",
                "total_ms",
                "citation_passed",
                "answer"
            ]
        )

        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "generated_at":
            datetime.now(UTC).isoformat()
            + "Z",

        "runs_per_query":
            RUNS_PER_QUERY,

        "total_runs":
            total_runs,

        "successful_runs":
            len(total_latencies),

        "citation_pass_rate":
            round(
                successful_citations
                / total_runs,
                4
            )
            if total_runs
            else 0,

        "retrieval_latency":
            calculate_stats(
                retrieval_latencies
            )
            if retrieval_latencies
            else {},

        "llm_latency":
            calculate_stats(
                llm_latencies
            )
            if llm_latencies
            else {},

        "end_to_end_latency":
            calculate_stats(
                total_latencies
            )
            if total_latencies
            else {}
    }

    json_path = os.path.join(
        results_dir,
        "rag_benchmark_summary.json"
    )

    with open(
        json_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            summary,
            f,
            indent=2
        )

    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)

    print(
        json.dumps(
            summary,
            indent=2
        )
    )

    print(
        "\nCSV:",
        csv_path
    )

    print(
        "JSON:",
        json_path
    )


if __name__ == "__main__":
    main()
