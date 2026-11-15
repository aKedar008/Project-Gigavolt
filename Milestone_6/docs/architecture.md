# Milestone 6 Architecture

```mermaid
flowchart LR
    A[New Files] --> B[Milestone 6 Orchestrator]
    B --> C{SHA-256 Manifest}
    C -->|New / Changed| D[Validation + Cleaning]
    C -->|Unchanged| E[Skip]
    D --> F[MariaDB Incremental Upsert]
    D --> G[MongoDB Incremental Upsert]
    D --> H[Document Chunking]
    H --> I[all-MiniLM-L6-v2 Embeddings]
    I --> J[ChromaDB gigavolt_m4]
    F --> K[M5 Hybrid Retriever]
    G --> K
    J --> K
    K --> L[RAG Context + S# Provenance]
    L --> M[OpenAI LLM]
    M --> N[Citation Validation]
    N --> O[Benchmark + P50/P95/P99 + QPS]
```

## Design decisions

Milestone 6 is an orchestration and optimization layer over the existing semester work rather than a replacement.

- MariaDB reuses the Milestone 5 `gigavolt_m5` database.
- MongoDB reuses the Milestone 5 `gigavolt.telemetry` collection.
- ChromaDB reuses the Milestone 4 `gigavolt_m4` collection.
- SHA-256 hashes provide new/changed/unchanged detection.
- SQL and MongoDB use upsert-style loading.
- Changed documents delete only their previous source chunks before re-indexing.
- The M5 hybrid retriever and RAG provenance format are reused.
- Optimization is deliberately small: targeted database indexes plus a bounded process-local cache.
- Neo4j/graph ingestion is omitted because that requirement was dropped for this project.
