"""
FAISS Index Builder for UNKNOWN

Generates semantic embeddings for every document chunk and
builds a FAISS vector index for semantic retrieval.
"""

import json
import numpy as np
import faiss

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

        # Extract chunk text
        texts = [chunk["text"] for chunk in chunks]

        logger.info("Generating semantic embeddings...")

        embeddings = embed_texts(texts)

        embeddings = np.array(embeddings, dtype=np.float32)

        logger.info(f"Embedding matrix shape: {embeddings.shape}")

        dimension = embeddings.shape[1]

        # Inner Product + normalized embeddings = cosine similarity
        index = faiss.IndexFlatIP(dimension)

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