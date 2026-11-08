
import chromadb
from sentence_transformers import SentenceTransformer


# Existing Milestone 4 configuration
CHROMA_PATH = "/opt/gigavolt-milestone4/chroma_db"
COLLECTION_NAME = "gigavolt_m4"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class VectorRetriever:

    def __init__(self):

        print("Connecting to Milestone 4 ChromaDB...")

        self.client = chromadb.PersistentClient(
            path=CHROMA_PATH
        )

        self.collection = self.client.get_collection(
            name=COLLECTION_NAME
        )

        print(
            "Connected successfully.",
            "Stored chunks:", self.collection.count()
        )

        print("Loading embedding model...")

        self.embedder = SentenceTransformer(
            EMBEDDING_MODEL
        )

        print("Embedding model loaded.")

    def retrieve(self, question, limit=4):

        if self.collection.count() == 0:
            return []

        # Convert natural-language question into an embedding
        query_embedding = self.embedder.encode(
            [question],
            normalize_embeddings=True
        )[0].tolist()

        # Search existing ChromaDB collection
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(limit, self.collection.count()),
            include=[
                "documents",
                "metadatas",
                "distances"
            ]
        )

        evidence = []

        for i in range(len(results["ids"][0])):

            metadata = results["metadatas"][0][i] or {}

            document = results["documents"][0][i]

            distance = results["distances"][0][i]

            document_name = metadata.get(
                "source_document",
                "Unknown document"
            )

            chunk_index = metadata.get(
                "chunk_index",
                "Unknown"
            )

            source_id = results["ids"][0][i]

            evidence.append({

                "source_type": "vector",

                "source_id": source_id,

                "source_name": document_name,

                "chunk_index": chunk_index,

                "timestamp": metadata.get(
                    "ingested_at_utc"
                ),

                "content": document,

                "distance": round(float(distance), 4),

                "citation": (
                    f"[VECTOR:{document_name}"
                    f"#chunk-{chunk_index}]"
                )

            })

        return evidence


if __name__ == "__main__":

    retriever = VectorRetriever()

    question = (
        "What are the common failure modes of "
        "X-7000 batteries in high-temperature "
        "environments, particularly inverter "
        "and thermal-related failures?"
    )

    print("\nQUESTION:")
    print(question)

    print("\nRETRIEVED EVIDENCE:")

    results = retriever.retrieve(question, limit=4)

    for i, result in enumerate(results, 1):

        print("\n" + "=" * 65)

        print(f"RESULT {i}")

        print("Source:", result["source_name"])

        print("Chunk:", result["chunk_index"])

        print("Distance:", result["distance"])

        print("Citation:", result["citation"])

        print("\nCONTENT:")

        print(result["content"][:1000])

    print("\n" + "=" * 65)

    print("Total retrieved chunks:", len(results))

