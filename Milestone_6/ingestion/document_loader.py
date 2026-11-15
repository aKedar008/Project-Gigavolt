from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

ROOT = Path.home() / "gigavolt-milestone6"

sys.path.insert(0, str(ROOT / "orchestration"))
sys.path.insert(0, str(ROOT / "ingestion"))

from manifest import check_file, mark_processed, mark_failed
from vector_pipeline import (
    read_document,
    chunk_text,
    stable_id,
    estimate_tokens,
)

CHROMA_PATH = "/opt/gigavolt-milestone4/chroma_db"
COLLECTION_NAME = "gigavolt_m4"
MODEL_NAME = "all-MiniLM-L6-v2"

CHUNK_TOKENS = 384
OVERLAP_TOKENS = 64


def ingest_document(path: Path):
    path = path.resolve()

    state = check_file(path)

    print(f"{state['status']}: {state['path']}")

    if state["status"] == "UNCHANGED":
        print("Skipping unchanged document.")
        return {
            "status": "SKIPPED",
            "chunks": 0
        }

    try:
        text = read_document(path)

        if not text.strip():
            raise ValueError("document contains no readable text")

        chunks = chunk_text(
            text,
            chunk_tokens=CHUNK_TOKENS,
            overlap_tokens=OVERLAP_TOKENS
        )

        if not chunks:
            raise ValueError("document produced no chunks")

        client = chromadb.PersistentClient(
            path=CHROMA_PATH
        )

        collection = client.get_collection(
            COLLECTION_NAME
        )

        source_name = path.name

        # Remove old chunks for this document before re-indexing.
        collection.delete(
            where={
                "source_document": source_name
            }
        )

        model = SentenceTransformer(
            MODEL_NAME
        )

        ids = []
        metadatas = []

        for index, chunk in enumerate(chunks):
            ids.append(
                stable_id(
                    source_name,
                    index,
                    chunk
                )
            )

            metadatas.append({
                "source_document": source_name,
                "source_extension": path.suffix.lower(),
                "chunk_index": index,
                "chunk_tokens_est": estimate_tokens(chunk),
                "chunk_chars": len(chunk),
                "ingested_at_utc": datetime.now(
                    timezone.utc
                ).isoformat()
            })

        embeddings = model.encode(
            chunks,
            normalize_embeddings=True
        ).tolist()

        collection.add(
            ids=ids,
            documents=chunks,
            metadatas=metadatas,
            embeddings=embeddings
        )

        mark_processed(
            path,
            stage="chromadb-document"
        )

        print(
            f"Indexed {len(chunks)} chunk(s). "
            f"Collection count: {collection.count()}"
        )

        return {
            "status": "SUCCESS",
            "chunks": len(chunks),
            "collection_count": collection.count()
        }

    except Exception as exc:
        mark_failed(
            path,
            error=str(exc),
            stage="chromadb-document"
        )

        raise


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "file",
        type=Path
    )

    args = parser.parse_args()

    result = ingest_document(
        args.file
    )

    print(
        json.dumps(
            result,
            indent=2
        )
    )
