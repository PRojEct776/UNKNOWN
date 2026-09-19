"""
BM25 Index Builder for UNKNOWN

Builds a BM25 lexical retrieval index from chunks.json
and saves it as bm25_index.pkl.
"""

import json
import pickle

from rank_bm25 import BM25Okapi

from app.rag.config import settings
from app.rag.logger import logger
from app.rag.query_processor import tokenize_text


class BM25IndexBuilder:
    """
    Builds and saves a BM25 index from chunked documents.
    """

    def __init__(self):
        # Ensure vector storage directory exists.
        settings.VECTOR_DIR.mkdir(parents=True, exist_ok=True)

    def build_index(self):
        """
        Build the BM25 index from chunks.json.

        Returns:
            tuple: (bm25_index, chunks)
        """

        chunk_file = settings.CHUNK_DIR / "chunks.json"

        logger.info(f"Loading chunks from: {chunk_file}")

        with open(chunk_file, "r", encoding="utf-8") as file:
            chunks = json.load(file)

        logger.info(f"Loaded {len(chunks)} chunks.")

        # Tokenize every chunk for BM25 indexing.
        corpus = [tokenize_text(chunk["text"]) for chunk in chunks]

        logger.info("Building BM25 index...")

        bm25 = BM25Okapi(corpus)

        output_path = settings.VECTOR_DIR / "bm25_index.pkl"

        with open(output_path, "wb") as file:
            pickle.dump(bm25, file)

        logger.info(f"BM25 index saved to: {output_path}")

        return bm25, chunks


# ---------------------- TEST BLOCK ---------------------- #

if __name__ == "__main__":

    builder = BM25IndexBuilder()

    bm25, chunks = builder.build_index()

    print("\n========== BM25 INDEX TEST ==========")
    print(f"Documents Indexed : {len(chunks)}")
    print(f"Vocabulary Size   : {len(bm25.idf)}")

    if chunks:
        sample = chunks[0]
        print("\nSample Indexed Chunk")
        print(f"Chunk ID : {sample['chunk_id']}")
        print(f"Document : {sample['document']}")
        print(f"Page     : {sample['page']}")
        print(f"Preview  : {sample['text'][:150]}...")

    print("=====================================")