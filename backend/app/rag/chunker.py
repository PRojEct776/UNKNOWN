"""
Chunking Engine for UNKNOWN

Reads processed JSON documents and converts page text into
overlapping chunks for BM25 and FAISS indexing.
"""

import json

from app.rag.config import settings
from app.rag.logger import logger


class DocumentChunker:
    """
    Splits page text into overlapping chunks.
    """

    def __init__(self):
        self.chunk_size = settings.CHUNK_SIZE
        self.chunk_overlap = settings.CHUNK_OVERLAP

        # Ensure the chunks directory exists
        settings.CHUNK_DIR.mkdir(parents=True, exist_ok=True)

    def split_text(self, text: str):
        """
        Split text into overlapping word chunks.

        Returns:
            list[str]: List of chunk strings.
        """
        words = text.split()

        if not words:
            return []

        chunks = []
        step = self.chunk_size - self.chunk_overlap

        for start in range(0, len(words), step):
            end = start + self.chunk_size

            chunk = " ".join(words[start:end]).strip()

            if chunk:
                chunks.append(chunk)

            if end >= len(words):
                break

        return chunks

    def create_chunks(self):
        """
        Read all JSON documents and create overlapping chunks.

        Returns:
            list: List of chunk dictionaries.
        """
        all_chunks = []
        chunk_counter = 1

        json_files = sorted(settings.JSON_DIR.glob("*.json"))

        logger.info(f"Found {len(json_files)} JSON documents.")

        for json_file in json_files:

            logger.info(f"Processing: {json_file.name}")

            with open(json_file, "r", encoding="utf-8") as file:
                document = json.load(file)

            # Matches document_loader.py schema
            document_name = document["source_file"]

            for page in document["pages"]:

                # Matches document_loader.py schema
                page_number = page["page_number"]
                page_text = page["text"]

                page_chunks = self.split_text(page_text)

                for chunk_text in page_chunks:

                    all_chunks.append(
                        {
                            "chunk_id": f"chunk_{chunk_counter}",
                            "document": document_name,
                            "page": page_number,
                            "text": chunk_text,
                        }
                    )

                    chunk_counter += 1

        output_path = settings.CHUNK_DIR / "chunks.json"

        with open(output_path, "w", encoding="utf-8") as file:
            json.dump(all_chunks, file, indent=4, ensure_ascii=False)

        logger.info(f"Created {len(all_chunks)} chunks.")
        logger.info(f"Chunks saved to: {output_path}")

        return all_chunks


# ---------------------- TEST BLOCK ---------------------- #

if __name__ == "__main__":

    chunker = DocumentChunker()

    chunks = chunker.create_chunks()

    print("\n========== CHUNKER TEST ==========")
    print(f"Chunk Size      : {settings.CHUNK_SIZE}")
    print(f"Chunk Overlap   : {settings.CHUNK_OVERLAP}")
    print(f"Total Chunks    : {len(chunks)}")

    if chunks:
        print("\nFirst Chunk")
        print(f"Chunk ID        : {chunks[0]['chunk_id']}")
        print(f"Document        : {chunks[0]['document']}")
        print(f"Page            : {chunks[0]['page']}")
        print(f"Preview         : {chunks[0]['text'][:150]}...")

    print("==================================")