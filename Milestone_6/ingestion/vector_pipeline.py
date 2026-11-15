#!/usr/bin/env python3
"""
Gigavolt Milestone 4 Vector Pipeline

Modes:
  ingest    - chunk documents, generate embeddings, store in ChromaDB
  search    - run interactive similarity search
  benchmark - measure vector retrieval latency and recall proxy

Example commands:
  python gigavolt_m4_pipeline.py ingest --rebuild
  python gigavolt_m4_pipeline.py search
  python gigavolt_m4_pipeline.py benchmark
"""

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import chromadb
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from docx import Document
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


DEFAULT_DATA_DIR = "/opt/gigavolt-milestone4/data"
DEFAULT_CHROMA_DIR = "/opt/gigavolt-milestone4/chroma_db"
DEFAULT_COLLECTION = "gigavolt_m4"
DEFAULT_MODEL = "all-MiniLM-L6-v2"

DEFAULT_CHUNK_TOKENS = 384
DEFAULT_OVERLAP_TOKENS = 64
DEFAULT_BATCH_SIZE = 32
DEFAULT_K = 5

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".html",
    ".htm",
    ".xml",
    ".docx",
    ".log",
    ".sql",
}


# ---------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """
    Approximate token count.

    This is not exact tokenizer logic, but it is good enough for
    256-512 token-style chunking.
    """
    words = re.findall(r"\S+", text)
    return int(len(words) * 1.3)


def normalize_text(text: str) -> str:
    """
    Normalize whitespace and remove null characters.
    """
    if not text:
        return ""

    text = text.replace("\x00", " ")
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def stable_id(source: str, chunk_index: int, text: str) -> str:
    """
    Create stable deterministic ID for each chunk.
    """
    raw = f"{source}|{chunk_index}|{text[:120]}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------
# Document loading
# ---------------------------------------------------------------------

def read_pdf(path: Path) -> str:
    parts = []

    try:
        reader = PdfReader(str(path))

        for i, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text() or ""

                if page_text.strip():
                    parts.append(f"\n\n--- Page {i + 1} ---\n{page_text}")

            except Exception as e:
                print(f"WARNING: Could not extract page {i + 1} from {path}: {e}")

    except Exception as e:
        print(f"WARNING: Could not read PDF {path}: {e}")

    return normalize_text("\n".join(parts))


def read_docx(path: Path) -> str:
    try:
        doc = Document(str(path))
        return normalize_text("\n".join(p.text for p in doc.paragraphs))
    except Exception as e:
        print(f"WARNING: Could not read DOCX {path}: {e}")
        return ""


def read_html(path: Path) -> str:
    try:
        raw = path.read_text(errors="ignore")
        soup = BeautifulSoup(raw, "lxml")
        return normalize_text(soup.get_text(separator=" "))
    except Exception as e:
        print(f"WARNING: Could not read HTML/XML {path}: {e}")
        return ""


def read_text(path: Path) -> str:
    try:
        return normalize_text(path.read_text(errors="ignore"))
    except Exception as e:
        print(f"WARNING: Could not read text file {path}: {e}")
        return ""


def read_document(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return read_pdf(path)

    if suffix == ".docx":
        return read_docx(path)

    if suffix in {".html", ".htm", ".xml"}:
        return read_html(path)

    return read_text(path)


def find_documents(data_dir: Path):
    docs = []

    for path in data_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            docs.append(path)

    return sorted(docs)


# ---------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------

def split_sentences(text: str):
    """
    Sentence-boundary aware splitting.

    This avoids most mid-sentence chunk boundaries.
    """
    text = normalize_text(text)

    if not text:
        return []

    pieces = []

    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()

        if not paragraph:
            continue

        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", paragraph)
        pieces.extend(sentences)

    return [p.strip() for p in pieces if p.strip()]


def split_long_sentence(sentence: str, max_tokens: int):
    """
    If a sentence, table row, or extracted text block is longer than the target
    chunk size, split it by words.
    """
    if estimate_tokens(sentence) <= max_tokens:
        return [sentence]

    words = sentence.split()
    approx_words = max(50, int(max_tokens / 1.3))

    chunks = []

    for i in range(0, len(words), approx_words):
        chunk = " ".join(words[i:i + approx_words]).strip()

        if chunk:
            chunks.append(chunk)

    return chunks


def chunk_text(text: str, chunk_tokens: int, overlap_tokens: int):
    """
    Creates overlapping, sentence-aware chunks.
    """
    sentences = []

    for sentence in split_sentences(text):
        sentences.extend(split_long_sentence(sentence, chunk_tokens))

    chunks = []
    current = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = estimate_tokens(sentence)

        if current and current_tokens + sentence_tokens > chunk_tokens:
            chunks.append(" ".join(current).strip())

            overlap = []
            overlap_count = 0

            for previous in reversed(current):
                previous_tokens = estimate_tokens(previous)

                if overlap_count + previous_tokens > overlap_tokens:
                    break

                overlap.insert(0, previous)
                overlap_count += previous_tokens

            current = overlap[:]
            current_tokens = overlap_count

        current.append(sentence)
        current_tokens += sentence_tokens

    if current:
        chunks.append(" ".join(current).strip())

    return [c for c in chunks if c]


# ---------------------------------------------------------------------
# ChromaDB collection
# ---------------------------------------------------------------------

def get_collection(
    chroma_dir,
    collection_name,
    rebuild=False,
    hnsw_m=16,
    hnsw_ef_construction=200,
    hnsw_ef_search=50,
):
    client = chromadb.PersistentClient(path=chroma_dir)

    if rebuild:
        try:
            client.delete_collection(collection_name)
            print(f"Deleted existing collection: {collection_name}")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={
            "description": "Gigavolt Milestone 4 vector search collection",
            "embedding_model": DEFAULT_MODEL,
            "hnsw:space": "cosine",
            "hnsw:M": hnsw_m,
            "hnsw:construction_ef": hnsw_ef_construction,
            "hnsw:search_ef": hnsw_ef_search,
        },
    )

    return collection


# ---------------------------------------------------------------------
# Ingest mode
# ---------------------------------------------------------------------

def ingest(args):
    data_dir = Path(args.data_dir).resolve()
    chroma_dir = Path(args.chroma_dir).resolve()

    chroma_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Gigavolt Milestone 4 - Ingestion")
    print("=" * 70)
    print(f"Data directory: {data_dir}")
    print(f"Chroma directory: {chroma_dir}")
    print(f"Collection: {args.collection}")
    print(f"Model: {args.model}")
    print(f"Chunk tokens: {args.chunk_tokens}")
    print(f"Overlap tokens: {args.overlap_tokens}")
    print(f"HNSW M: {args.hnsw_m}")
    print(f"HNSW ef_construction: {args.hnsw_ef_construction}")
    print(f"HNSW ef_search: {args.hnsw_ef_search}")
    print("=" * 70)

    docs = find_documents(data_dir)
    print(f"Found {len(docs)} supported document(s).")

    if not docs:
        print("No supported documents found. Check your data directory.")
        return

    print("Loading embedding model...")
    embedder = SentenceTransformer(args.model)

    collection = get_collection(
        chroma_dir=str(chroma_dir),
        collection_name=args.collection,
        rebuild=args.rebuild,
        hnsw_m=args.hnsw_m,
        hnsw_ef_construction=args.hnsw_ef_construction,
        hnsw_ef_search=args.hnsw_ef_search,
    )

    ids = []
    texts = []
    metadatas = []

    start_time = time.time()

    for doc_path in tqdm(docs, desc="Reading and chunking"):
        text = read_document(doc_path)

        if not text.strip():
            continue

        chunks = chunk_text(
            text,
            chunk_tokens=args.chunk_tokens,
            overlap_tokens=args.overlap_tokens,
        )

        relative_source = str(doc_path.relative_to(data_dir))

        for i, chunk in enumerate(chunks):
            ids.append(stable_id(relative_source, i, chunk))
            texts.append(chunk)
            metadatas.append(
                {
                    "source_document": relative_source,
                    "source_extension": doc_path.suffix.lower(),
                    "chunk_index": i,
                    "chunk_tokens_est": estimate_tokens(chunk),
                    "chunk_chars": len(chunk),
                    "ingested_at_utc": datetime.now(timezone.utc).isoformat(),
                }
            )

    print(f"Prepared {len(texts)} chunk(s).")

    if not texts:
        print("No chunks generated.")
        return

    print("Embedding and storing chunks...")

    for i in tqdm(range(0, len(texts), args.batch_size), desc="Embedding batches"):
        batch_texts = texts[i:i + args.batch_size]
        batch_ids = ids[i:i + args.batch_size]
        batch_meta = metadatas[i:i + args.batch_size]

        embeddings = embedder.encode(
            batch_texts,
            batch_size=args.batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        ).tolist()

        collection.add(
            ids=batch_ids,
            documents=batch_texts,
            metadatas=batch_meta,
            embeddings=embeddings,
        )

    elapsed = time.time() - start_time

    summary = {
        "document_count": len(docs),
        "chunk_count": len(texts),
        "collection_count": collection.count(),
        "embedding_model": args.model,
        "chunk_tokens": args.chunk_tokens,
        "overlap_tokens": args.overlap_tokens,
        "hnsw_m": args.hnsw_m,
        "hnsw_ef_construction": args.hnsw_ef_construction,
        "hnsw_ef_search": args.hnsw_ef_search,
        "elapsed_seconds": elapsed,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    Path("ingestion_summary.json").write_text(json.dumps(summary, indent=2))

    print("=" * 70)
    print("Ingestion complete")
    print("=" * 70)
    print(json.dumps(summary, indent=2))
    print("\nFile written: ingestion_summary.json")


# ---------------------------------------------------------------------
# Search mode
# ---------------------------------------------------------------------

def search(args):
    print("=" * 70)
    print("Gigavolt Milestone 4 - Interactive Search")
    print("=" * 70)

    print("Loading embedding model...")
    embedder = SentenceTransformer(args.model)

    client = chromadb.PersistentClient(path=args.chroma_dir)
    collection = client.get_collection(args.collection)

    print(f"Collection count: {collection.count()}")
    print("Type a query or 'quit' to exit.")

    while True:
        query = input("\nQuery: ").strip()

        if query.lower() in {"quit", "exit", "q"}:
            print("Goodbye.")
            break

        if not query:
            continue

        embedding_start = time.perf_counter()
        query_embedding = embedder.encode(
            [query],
            normalize_embeddings=True,
        ).tolist()[0]
        embedding_ms = (time.perf_counter() - embedding_start) * 1000

        search_start = time.perf_counter()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=args.k,
            include=["documents", "metadatas", "distances"],
        )
        search_ms = (time.perf_counter() - search_start) * 1000

        print(f"\nEmbedding time: {embedding_ms:.2f} ms")
        print(f"Vector DB search time: {search_ms:.2f} ms")

        ids = results["ids"][0]
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0]

        if not ids:
            print("No results found.")
            continue

        for i, doc_id in enumerate(ids):
            doc = docs[i]
            meta = metas[i]
            dist = distances[i]
            similarity = 1 - dist

            snippet = doc[:500].replace("\n", " ")

            if len(doc) > 500:
                snippet += "..."

            print("-" * 70)
            print(f"[{i + 1}] Similarity: {similarity:.4f}")
            print(f"ID: {doc_id}")
            print(f"Source: {meta.get('source_document')}")
            print(f"Chunk index: {meta.get('chunk_index')}")
            print(f"Snippet: {snippet}")


# ---------------------------------------------------------------------
# Benchmark mode
# ---------------------------------------------------------------------

def exact_top_k(query_embedding, all_embeddings, all_ids, k):
    q = np.array(query_embedding, dtype=np.float32)
    emb = np.array(all_embeddings, dtype=np.float32)

    q = q / max(np.linalg.norm(q), 1e-12)

    emb_norms = np.linalg.norm(emb, axis=1, keepdims=True)
    emb = emb / np.maximum(emb_norms, 1e-12)

    sims = emb @ q
    top_idx = np.argsort(-sims)[:k]

    return [all_ids[i] for i in top_idx]


def benchmark(args):
    print("=" * 70)
    print("Gigavolt Milestone 4 - Benchmark")
    print("=" * 70)

    benchmark_queries = [
        "inverter fault troubleshooting",
        "battery maintenance procedure",
        "warranty claim denial reason",
        "dispatch technician repair summary",
        "equipment voltage capacity",
        "replacement parts reorder level",
        "customer service record",
        "installation safety procedure",
        "solar panel service issue",
        "preventive maintenance schedule",
    ]

    print("Loading embedding model...")
    embedder = SentenceTransformer(args.model)

    client = chromadb.PersistentClient(path=args.chroma_dir)
    collection = client.get_collection(args.collection)

    print(f"Collection count: {collection.count()}")

    print("Loading all embeddings for exact recall comparison...")
    all_data = collection.get(include=["embeddings"])
    all_ids = all_data["ids"]
    all_embeddings = all_data["embeddings"]

    if not all_ids:
        print("No vectors found. Run ingest first.")
        return

    latencies = []
    recalls = []
    rows = []

    warmup = embedder.encode(["warm up"], normalize_embeddings=True).tolist()[0]

    for _ in range(5):
        collection.query(query_embeddings=[warmup], n_results=args.k)

    for query in benchmark_queries:
        query_embedding = embedder.encode(
            [query],
            normalize_embeddings=True,
        ).tolist()[0]

        exact_ids = exact_top_k(query_embedding, all_embeddings, all_ids, args.k)
        exact_set = set(exact_ids)

        for run in range(args.runs_per_query):
            start = time.perf_counter()

            result = collection.query(
                query_embeddings=[query_embedding],
                n_results=args.k,
                include=["distances"],
            )

            latency_ms = (time.perf_counter() - start) * 1000
            returned_ids = result["ids"][0]

            recall_at_k = len(set(returned_ids) & exact_set) / args.k

            latencies.append(latency_ms)
            recalls.append(recall_at_k)

            rows.append(
                {
                    "query": query,
                    "run": run + 1,
                    "latency_ms": latency_ms,
                    "recall_at_k": recall_at_k,
                    "returned_ids": "|".join(returned_ids),
                    "exact_ids": "|".join(exact_ids),
                }
            )

    df = pd.DataFrame(rows)
    df.to_csv("benchmark_results.csv", index=False)

    summary = {
        "k": args.k,
        "runs_per_query": args.runs_per_query,
        "query_count": len(benchmark_queries),
        "latency_ms_mean": float(np.mean(latencies)),
        "latency_ms_p50": float(np.percentile(latencies, 50)),
        "latency_ms_p95": float(np.percentile(latencies, 95)),
        "latency_ms_p99": float(np.percentile(latencies, 99)),
        "recall_at_k_mean": float(np.mean(recalls)),
        "recall_at_k_min": float(np.min(recalls)),
        "sub_20ms_median_pass": bool(np.percentile(latencies, 50) < 20),
        "recall_0_9_pass": bool(np.mean(recalls) >= 0.9),
    }

    Path("benchmark_summary.json").write_text(json.dumps(summary, indent=2))

    print("=" * 70)
    print("Benchmark complete")
    print("=" * 70)
    print(json.dumps(summary, indent=2))
    print("\nFiles written:")
    print("  benchmark_results.csv")
    print("  benchmark_summary.json")


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Gigavolt Milestone 4 vector pipeline"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_options(p):
        p.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
        p.add_argument("--chroma-dir", default=DEFAULT_CHROMA_DIR)
        p.add_argument("--collection", default=DEFAULT_COLLECTION)
        p.add_argument("--model", default=DEFAULT_MODEL)
        p.add_argument("--k", type=int, default=DEFAULT_K)

    ingest_parser = subparsers.add_parser("ingest")
    add_common_options(ingest_parser)
    ingest_parser.add_argument("--chunk-tokens", type=int, default=DEFAULT_CHUNK_TOKENS)
    ingest_parser.add_argument("--overlap-tokens", type=int, default=DEFAULT_OVERLAP_TOKENS)
    ingest_parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    ingest_parser.add_argument("--rebuild", action="store_true")
    ingest_parser.add_argument("--hnsw-m", type=int, default=16)
    ingest_parser.add_argument("--hnsw-ef-construction", type=int, default=200)
    ingest_parser.add_argument("--hnsw-ef-search", type=int, default=50)
    ingest_parser.set_defaults(func=ingest)

    search_parser = subparsers.add_parser("search")
    add_common_options(search_parser)
    search_parser.set_defaults(func=search)

    benchmark_parser = subparsers.add_parser("benchmark")
    add_common_options(benchmark_parser)
    benchmark_parser.add_argument("--runs-per-query", type=int, default=10)
    benchmark_parser.set_defaults(func=benchmark)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()