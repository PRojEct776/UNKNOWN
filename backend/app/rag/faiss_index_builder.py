"""
FAISS Index Builder for UNKNOWN

Generates semantic embeddings for every document chunk and
builds a FAISS vector index for semantic retrieval.
"""

import json

import faiss
import numpy as np

from app.rag.config import settings
from app.rag.embedder import embed_texts
from app.rag.logger import logger


class FAISSIndexBuilder:
    """
    Builds and saves a FAISS semantic index.
    """

    def __init__(self):
        settings.VECTOR_DIR.mkdir(parents=True, exist_ok=True)

    def build_index(self):
        """
        Build FAISS index from chunks.json.

        Returns:
            tuple: (faiss_index, metadata)
        """

        chunk_file = settings.CHUNK_DIR / "chunks.json"

        logger.info(f"Loading chunks from: {chunk_file}")

        with open(chunk_file, "r", encoding="utf-8") as file:
            chunks = json.load(file)

        logger.info(f"Loaded {len(chunks)} chunks.")

        # Check for reusable cached embeddings from prior build
        embedding_path = settings.VECTOR_DIR / "chunk_embeddings.npy"
        metadata_path = settings.VECTOR_DIR / "faiss_metadata.json"
        cached_lookup: dict[tuple[str, int, str], np.ndarray] = {}

        if embedding_path.exists() and metadata_path.exists():
            try:
                cached_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
                cached_matrix = np.load(embedding_path)
                if len(cached_meta) == len(cached_matrix):
                    for idx, meta_item in enumerate(cached_meta):
                        key = (
                            meta_item.get("document", ""),
                            meta_item.get("page", 0),
                            meta_item.get("text", "").strip(),
                        )
                        cached_lookup[key] = cached_matrix[idx]
            except Exception as cache_err:
                logger.warning("Could not read previous FAISS cache: %s", cache_err)

        if not chunks:
            dimension = 384
            index = faiss.IndexFlatIP(dimension)
            embeddings = np.empty((0, dimension), dtype=np.float32)
        else:
            needed_texts: list[str] = []
            needed_indices: list[int] = []
            assembled_embeddings: list[np.ndarray | None] = [None] * len(chunks)

            for i, chunk in enumerate(chunks):
                key = (
                    chunk.get("document", ""),
                    chunk.get("page", 0),
                    chunk.get("text", "").strip(),
                )
                if key in cached_lookup:
                    assembled_embeddings[i] = cached_lookup[key]
                else:
                    needed_texts.append(chunk["text"])
                    needed_indices.append(i)

            if needed_texts:
                logger.info(f"Generating semantic embeddings for {len(needed_texts)} new/updated chunks...")
                new_embs = embed_texts(needed_texts)
                for chunk_idx, emb in zip(needed_indices, new_embs):
                    assembled_embeddings[chunk_idx] = emb
            else:
                logger.info(f"Reusing all {len(chunks)} cached chunk embeddings.")

            embeddings = np.array(assembled_embeddings, dtype=np.float32)
            logger.info(f"Embedding matrix shape: {embeddings.shape}")
            dimension = embeddings.shape[1] if embeddings.shape[0] > 0 else 384
            # Inner Product + normalized embeddings = cosine similarity
            index = faiss.IndexFlatIP(dimension)
            if embeddings.shape[0] > 0:
                index.add(embeddings)

        logger.info(f"Indexed {index.ntotal} vectors.")

        # Save FAISS index
        index_path = settings.VECTOR_DIR / "faiss.index"
        faiss.write_index(index, str(index_path))

        # Save embedding matrix
        embedding_path = settings.VECTOR_DIR / "chunk_embeddings.npy"
        np.save(embedding_path, embeddings)

        # Save metadata (chunk lookup)
        metadata_path = settings.VECTOR_DIR / "faiss_metadata.json"

        with open(metadata_path, "w", encoding="utf-8") as file:
            json.dump(chunks, file, indent=4, ensure_ascii=False)

        logger.info(f"FAISS index saved to: {index_path}")
        logger.info(f"Embeddings saved to: {embedding_path}")
        logger.info(f"Metadata saved to: {metadata_path}")

        return index, chunks, embeddings


# ---------------------- TEST BLOCK ---------------------- #

if __name__ == "__main__":

    builder = FAISSIndexBuilder()

    index, metadata, embeddings = builder.build_index()

    print("\n========== FAISS INDEX TEST ==========")
    print(f"Chunks Indexed     : {len(metadata)}")
    print(f"Vector Dimension   : {embeddings.shape[1]}")
    print(f"Embedding Shape    : {embeddings.shape}")
    print(f"Vectors in Index   : {index.ntotal}")

    if metadata:
        sample = metadata[0]
        print("\nSample Metadata")
        print(f"Chunk ID : {sample['chunk_id']}")
        print(f"Document : {sample['document']}")
        print(f"Page     : {sample['page']}")
        print(f"Preview  : {sample['text'][:120]}...")

    print("======================================")
