# Project Gigavolt - Milestone 6

Milestone 6 automates incremental ingestion, vector updates, RAG integration, optimization, benchmarking, and provenance validation while reusing Milestones 4 and 5.

## Components

- `orchestration/manifest.py` - SHA-256 new/changed/unchanged tracking.
- `orchestration/pipeline_orchestrator.py` - scans all incoming folders and runs the correct loader.
- `ingestion/telemetry_loader.py` - validates and upserts telemetry into MongoDB.
- `ingestion/sql_loader.py` - validates and upserts equipment records into MariaDB.
- `ingestion/document_loader.py` - incrementally chunks, embeds, and replaces changed ChromaDB chunks.
- `optimization/apply_indexes.py` - targeted MariaDB and MongoDB indexes.
- `optimization/cached_rag.py` - bounded process-local repeated-query cache.
- `benchmark/benchmark_m6.py` - 24-prompt benchmark with P50/P95/P99, throughput, citation and provenance metrics.
- `validation/provenance_audit.py` - citation-to-source metadata audit.
- `docs/architecture.md` - architecture and tradeoffs.
- `docs/demo_checklist.md` - screencast sequence.

## Reused systems

- MariaDB configuration: `~/gigavolt-milestone5/.env`
- MongoDB: `gigavolt.telemetry`
- ChromaDB: `/opt/gigavolt-milestone4/chroma_db`
- Collection: `gigavolt_m4`
- Embedding model: `all-MiniLM-L6-v2`
- RAG: `~/gigavolt-milestone5/rag/rag_pipeline.py`

No credentials are stored in Milestone 6.

## Run pipeline

```bash
cd ~/gigavolt-milestone6
python orchestration/pipeline_orchestrator.py
```

A second run with unchanged inputs should report `SKIPPED`.

## Apply optimization

```bash
python optimization/apply_indexes.py
```

## Benchmark

```bash
python benchmark/benchmark_m6.py
```

Outputs are written under `results/`.

## Provenance audit

```bash
python validation/provenance_audit.py
```

## Reliability

Each loader validates before database changes. MariaDB uses transactions and rollback. The manifest is updated only after successful processing. Failed files remain eligible for another run. The orchestrator logs failures and continues with independent files.
