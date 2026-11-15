#!/bin/bash

set -u

ROOT="$HOME/gigavolt-milestone6"
cd "$ROOT" || exit 1

pause() {
    echo
    echo "---------------------------------------------------------------------"
    read -p "Press ENTER when you are ready to continue..."
}

say() {
    echo
    echo "======================================================================"
    echo "                         SAY THIS"
    echo "======================================================================"
    echo "$1"
    echo "======================================================================"
}

clear

echo "======================================================================"
echo "        PROJECT GIGAVOLT - MILESTONE 6 VIDEO DEMONSTRATION"
echo " Automated Pipeline, Optimization & System Synthesis"
echo "======================================================================"

say "Hi, this is my demonstration of Project Gigavolt Milestone 6.

The purpose of this milestone was to integrate the systems developed in the previous milestones into an automated incremental pipeline, optimize the retrieval and RAG workflow, benchmark system performance, and validate source provenance.

The complete system runs on my AWS EC2 environment."

pause


# =====================================================================
# SECTION 1 - PROJECT STRUCTURE
# =====================================================================

clear

say "I will first show the overall structure of Milestone 6.

The project is separated into orchestration, ingestion, optimization, benchmarking, validation, documentation, and results.

This keeps the pipeline modular and makes the final system easier to reproduce and maintain."

echo
echo "==================== PROJECT STRUCTURE ================================"
echo

find . -maxdepth 2 -type f \
    ! -path "./state/*" \
    ! -name "*.pyc" \
    ! -name "*.bak" \
    | sort

echo
echo "Main components:"
echo "  orchestration/  -> pipeline orchestration and change detection"
echo "  ingestion/      -> telemetry, SQL, and document ingestion"
echo "  optimization/   -> database indexes and RAG caching"
echo "  benchmark/      -> 24-prompt benchmark"
echo "  validation/     -> provenance auditing"
echo "  docs/           -> architecture and demonstration documentation"
echo "  results/        -> benchmark and execution evidence"

pause


# =====================================================================
# SECTION 2 - ARCHITECTURE
# =====================================================================

clear

say "The final architecture combines three main data sources.

MongoDB stores operational telemetry.

MariaDB stores structured information such as equipment, service history, and warranty information.

ChromaDB contains vector embeddings generated from technical documents.

The hybrid retriever selects relevant evidence from these sources and assigns source identifiers such as S1, S2, and S3.

Only that retrieved evidence is sent to the hosted language model.

The final response is then checked against the provenance map so that citations can be traced back to their original source."

echo
echo "====================== ARCHITECTURE =================================="
echo

sed -n '1,140p' docs/architecture.md

pause


# =====================================================================
# SECTION 3 - PIPELINE ORCHESTRATION
# =====================================================================

clear

say "Next I will demonstrate the end-to-end pipeline orchestration.

The orchestrator checks incoming telemetry, relational data, and documents.

Instead of reprocessing everything every time, the system calculates a SHA-256 hash for each input file.

If a file has already been successfully processed and has not changed, the pipeline skips it.

This provides incremental processing and avoids unnecessary database loading, document chunking, and vector embedding."

echo
echo "=================== RUNNING ORCHESTRATOR ============================="
echo

python orchestration/pipeline_orchestrator.py

echo
echo "=================== LAST PIPELINE RUN ================================"
echo

if [ -f results/last_pipeline_run.json ]; then
python - <<'PY'
import json
from pathlib import Path

p = Path("results/last_pipeline_run.json")
d = json.loads(p.read_text())

print(json.dumps(d, indent=2))
PY
fi

say "Here we can see that previously processed files are being skipped.

That is expected behavior and demonstrates that the incremental change-detection logic is working correctly.

If a new file arrived or an existing file changed, only that item would be processed again."

pause


# =====================================================================
# SECTION 4 - MANIFEST
# =====================================================================

clear

say "The state of previously processed files is stored in a manifest.

The manifest records file hashes and processing status.

This allows the pipeline to determine whether an input is new, changed, or unchanged across executions."

echo
echo "==================== PIPELINE MANIFEST ==============================="
echo

if [ -f state/manifest.json ]; then
python - <<'PY'
import json
from pathlib import Path

d = json.loads(Path("state/manifest.json").read_text())
print(json.dumps(d, indent=2))
PY
fi

pause


# =====================================================================
# SECTION 5 - OPTIMIZATION
# =====================================================================

clear

say "Milestone 6 also required performance optimization.

I added database indexes to improve common MongoDB and MariaDB lookup patterns.

I also implemented a process-local response cache for repeated RAG questions.

The purpose of the benchmark is not only to report total latency, but also to identify which stage is responsible for most of the delay."

echo
echo "=================== OPTIMIZATION RESULTS ============================="
echo

if [ -f results/index_optimization.json ]; then
python - <<'PY'
import json
from pathlib import Path

d = json.loads(Path("results/index_optimization.json").read_text())
print(json.dumps(d, indent=2))
PY
else
    echo "Index optimization result file not found."
fi

echo
echo "Implemented optimization techniques:"
echo "  ✓ MongoDB indexing"
echo "  ✓ MariaDB indexing"
echo "  ✓ vector retrieval"
echo "  ✓ repeated-query caching"

pause


# =====================================================================
# SECTION 6 - BENCHMARK
# =====================================================================

clear

say "For performance evaluation, I created a benchmark containing 24 complex prompts.

The prompts include multi-source retrieval, technical-document lookup, operational telemetry, service history, warranty information, and diagnostic reasoning.

I am showing the saved benchmark results instead of rerunning all 24 prompts during this short demonstration."

echo
echo "====================== BENCHMARK RESULTS ============================="
echo

python - <<'PY'
import json
from pathlib import Path

p = Path("results/benchmark_m6_summary.json")

if not p.exists():
    print("Benchmark summary not found.")
    raise SystemExit()

d = json.loads(p.read_text())

cold = d["cold"]
warm = d["warm_cache"]

print("BENCHMARK COMPLETION")
print("--------------------")
print("Distinct prompts :", d["distinct_prompt_count"])
print("Successful runs  :", cold["successful_runs"])
print("Failed runs      :", cold["failed_runs"])
print("Citation pass    :", f'{cold["citation_pass_rate"] * 100:.2f}%')
print("Provenance pass  :", f'{cold["provenance_pass_rate"] * 100:.2f}%')

print("\nCOLD-PATH LATENCY")
print("-----------------")

for name in [
    "sql_ms",
    "mongo_ms",
    "vector_ms",
    "retrieval_total_ms",
    "llm_ms",
    "total_ms"
]:
    stats = cold["stage_latency"].get(name, {})
    if stats:
        print(
            f'{name:20s} '
            f'P50={stats.get("p50_ms",0):8.2f} ms  '
            f'P95={stats.get("p95_ms",0):8.2f} ms  '
            f'P99={stats.get("p99_ms",0):8.2f} ms'
        )

print("\nWARM-CACHE LATENCY")
print("------------------")
w = warm["stage_latency"]["total_ms"]

print("P50 :", w.get("p50_ms"), "ms")
print("P95 :", w.get("p95_ms"), "ms")
print("P99 :", w.get("p99_ms"), "ms")
print("QPS :", warm.get("throughput_qps"))

print("\nBOTTLENECK ANALYSIS")
print("-------------------")

retrieval = cold["stage_latency"]["retrieval_total_ms"]["p50_ms"]
llm = cold["stage_latency"]["llm_ms"]["p50_ms"]

print(f"Retrieval P50 : {retrieval:.2f} ms")
print(f"LLM P50       : {llm:.2f} ms")

if llm > retrieval:
    print("Finding: Hosted LLM generation is the dominant cold-path bottleneck.")
else:
    print("Finding: Retrieval is the dominant cold-path bottleneck.")

print("\nCACHE IMPACT")
print("------------")
print(
    "Cold P50:",
    cold["stage_latency"]["total_ms"]["p50_ms"],
    "ms"
)

print(
    "Warm-cache P50:",
    warm["stage_latency"]["total_ms"]["p50_ms"],
    "ms"
)
PY

say "The benchmark successfully completed all 24 prompts without runtime failures.

The stage-level profiling shows that retrieval itself is relatively fast.

The largest source of cold-path latency is the hosted language model generation stage.

This is important because it shows that the database and vector retrieval layers are not the primary bottleneck.

For repeated questions, the response cache avoids running both retrieval and generation again, which reduces response latency dramatically.

The cold end-to-end median is above the five-second target, so I would not claim that the uncached path meets that target.

Instead, the benchmark clearly identifies the external language model as the remaining cold-path bottleneck, while the optimized repeated-query path performs well below the target."

pause


# =====================================================================
# SECTION 7 - PROVENANCE
# =====================================================================

clear

say "Another major requirement of the milestone is provenance.

Every generated response should contain source identifiers that can be mapped back to the evidence retrieved by the system.

I created an automated provenance audit that checks the benchmark outputs and verifies that citations correspond to valid retrieved sources."

echo
echo "====================== PROVENANCE AUDIT =============================="
echo

python validation/provenance_audit.py

say "The final audit validates all 24 benchmark responses.

This gives the final benchmark 100 percent citation and provenance coverage.

The S-number identifiers can be traced back to MongoDB telemetry records, relational database evidence, or specific vector-document chunks."

pause


# =====================================================================
# SECTION 8 - SAMPLE RAG RESULT
# =====================================================================

clear

say "I will now show one saved RAG result from the benchmark.

This demonstrates how the answer, citation validation, and provenance metadata are stored together.

I am using an existing benchmark result rather than making another API request during the recording."

echo
echo "===================== SAMPLE RAG RESULT =============================="
echo

python - <<'PY'
import json
from pathlib import Path

p = Path("results/benchmark_m6_detailed.json")
d = json.loads(p.read_text())

rows = d.get("cold_results", [])

row = None

for r in rows:
    sources = r.get("sources", [])
    if len(sources) >= 2:
        row = r
        break

if row is None and rows:
    row = rows[0]

if row:
    print("QUESTION")
    print("--------")
    print(row.get("question"))

    print("\nANSWER")
    print("------")
    print(row.get("answer"))

    print("\nCITATION VALIDATION")
    print("-------------------")
    print(row.get("citation_validation"))

    print("\nPROVENANCE MAP")
    print("--------------")

    for citation, metadata in row.get("provenance", {}).items():
        print(citation, "=>", metadata)

else:
    print("No benchmark result available.")
PY

say "This example shows how the final answer remains connected to the evidence used to generate it.

Instead of treating the language model response as an unsupported answer, the system maintains a provenance map showing where each source came from."

pause


# =====================================================================
# SECTION 9 - FINAL SUMMARY
# =====================================================================

clear

echo "======================================================================"
echo "                    FINAL SYSTEM SUMMARY"
echo "======================================================================"
echo

python - <<'PY'
import json
from pathlib import Path

s = json.loads(
    Path("results/benchmark_m6_summary.json").read_text()
)

c = s["cold"]
w = s["warm_cache"]

print("✓ Incremental ingestion")
print("✓ SHA-256 change detection")
print("✓ MongoDB telemetry")
print("✓ MariaDB structured data")
print("✓ ChromaDB vector retrieval")
print("✓ Hybrid RAG retrieval")
print("✓ Database indexing")
print("✓ RAG response caching")
print("✓ 24 complex benchmark prompts")
print(
    "✓ Benchmark:",
    c["successful_runs"],
    "/",
    c["prompt_count"],
    "successful executions"
)
print(
    "✓ Citation coverage:",
    f'{c["citation_pass_rate"]*100:.2f}%'
)
print(
    "✓ Provenance coverage:",
    f'{c["provenance_pass_rate"]*100:.2f}%'
)
print(
    "✓ Warm-cache P50:",
    w["stage_latency"]["total_ms"]["p50_ms"],
    "ms"
)

print()
print("FINAL ARCHITECTURE")
print("------------------")
print("MongoDB + MariaDB + ChromaDB")
print("             ↓")
print("       Hybrid Retrieval")
print("             ↓")
print("     [S#] Evidence Context")
print("             ↓")
print("  Groq-hosted GPT-OSS Model")
print("             ↓")
print(" Citation Validation + Cache")
PY

say "To summarize, Milestone 6 combines the systems from the previous milestones into one reproducible workflow.

The system supports incremental ingestion, hybrid retrieval across structured and unstructured data, evidence-grounded RAG generation, database optimization, caching, performance benchmarking, and automated provenance validation.

The benchmark completed all 24 prompts successfully and achieved 100 percent provenance coverage.

The profiling also identified hosted LLM generation as the major remaining cold-path performance bottleneck, while repeated-query caching significantly improves response time.

That concludes my Project Gigavolt Milestone 6 demonstration."

echo
echo "======================================================================"
echo "                   DEMONSTRATION COMPLETE"
echo "======================================================================"
