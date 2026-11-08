# Gigavolt Milestone 5
## Multi-Model Integration and Hybrid RAG Retrieval Engine

### Architecture

The solution combines three data models:

1. MariaDB
   - Equipment metadata
   - Service history
   - Warranty claims

2. MongoDB
   - 200 professor-provided telemetry records
   - Equipment faults
   - Temperatures
   - Voltage/current
   - SOC and operational notes

3. ChromaDB
   - Reuses the Milestone 4 vector database
   - Collection: gigavolt_m4
   - 29 technical-document chunks
   - Semantic search using all-MiniLM-L6-v2

The Python hybrid retrieval layer dynamically routes natural-language
queries to the appropriate data sources and combines retrieved evidence
before sending grounded context to the LLM.

### RAG Pipeline

Natural-language query
-> Query routing
-> SQL / MongoDB / Vector retrieval
-> Evidence normalization
-> [S#] source assignment
-> LLM grounded generation
-> Citation validation
-> Provenance output
-> Performance measurement

### Data Provenance

Professor-provided telemetry and technical documents are kept separate
from synthetic demonstration service and warranty records.

Synthetic SQL records are explicitly stored with:

record_origin = synthetic_demo

The RAG prompt requires the model to disclose this designation whenever
such records are referenced.

### Test Queries

1. What are common failure modes for X-7000 batteries in high-temperature environments?

2. Show me service history for equipment SN-4829 and related warranty claims.

3. What maintenance actions are recommended after an X-7000 inverter fault?

### Benchmark

15 end-to-end RAG runs were performed.

Retrieval:
- P50: 42.94 ms
- P95: 414.54 ms
- P99: 496.14 ms

LLM:
- P50: 4173.08 ms
- P95: 5170.31 ms
- P99: 5200.21 ms

End-to-End:
- P50: 4283.18 ms
- P95: 5207.59 ms
- P99: 5226.72 ms

Citation validation pass rate:
- 100%

The median end-to-end latency is below five seconds.
Tail latency is dominated by external LLM generation rather than
local database retrieval.

### Main Files

retrieval/mongo_retriever.py
retrieval/vector_retriever.py
retrieval/sql_retriever.py
retrieval/hybrid_retriever.py
retrieval/sync_equipment.py

rag/rag_pipeline.py

benchmark_rag.py

results/rag_test_results.json
results/rag_benchmark.csv
results/rag_benchmark_summary.json

### Security

Database credentials and the OpenAI API key are stored in .env.

.env is excluded through .gitignore and should never be submitted
or committed to source control.
