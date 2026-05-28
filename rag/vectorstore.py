import os
from pathlib import Path

import chromadb
import voyageai
from dotenv import load_dotenv

from utils.pdf_parser import extract_text_from_pdf

load_dotenv()

_CHROMA_DIR = Path(__file__).parent / "chroma_db"
_COLLECTION_NAME = "legal_documents"
_VOYAGE_MODEL = "voyage-3"
_BATCH_SIZE = 128  # Voyage API max batch size


def split_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """
    Split text into overlapping chunks of ~chunk_size characters.
    Prefers paragraph > line > sentence > word boundaries over hard cuts.
    """
    if not text.strip():
        return []
    if len(text) <= chunk_size:
        return [text.strip()]

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        if end == len(text):
            tail = text[start:].strip()
            if tail:
                chunks.append(tail)
            break

        # Find the rightmost natural break within the window
        cut = end
        for sep in ("\n\n", "\n", ". ", " "):
            pos = text.rfind(sep, start + overlap, end)
            if pos != -1:
                cut = pos + len(sep)
                break

        chunk = text[start:cut].strip()
        if chunk:
            chunks.append(chunk)

        # Advance start while keeping overlap with the previous chunk
        start = max(start + 1, cut - overlap)

    return chunks


class VectorStore:
    def __init__(self, chroma_dir: str | None = None):
        path = chroma_dir or str(_CHROMA_DIR)
        self.chroma = chromadb.PersistentClient(path=path)
        self.collection = self.chroma.get_or_create_collection(_COLLECTION_NAME)
        self.voyage = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))

    def _embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        """Embed texts in batches to stay within Voyage API limits."""
        embeddings: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            result = self.voyage.embed(batch, model=_VOYAGE_MODEL, input_type=input_type)
            embeddings.extend(result.embeddings)
        return embeddings

    def index_pdf(self, pdf_path: str, source_name: str) -> int:
        """
        Extract text from a PDF, chunk it, embed the chunks, and store them in ChromaDB.
        Returns the number of chunks added, or 0 if this source is already indexed.
        """
        existing = self.collection.get(where={"source": source_name}, limit=1)
        if existing["ids"]:
            return 0

        # No character limit — index the full document for maximum RAG coverage
        text, _ = extract_text_from_pdf(pdf_path, max_chars=None)
        chunks = split_text(text)
        if not chunks:
            return 0

        embeddings = self._embed(chunks, input_type="document")
        ids = [f"{source_name}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"source": source_name, "chunk_index": i} for i in range(len(chunks))]

        self.collection.add(
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )
        return len(chunks)

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Return the top-k most relevant chunks for the query.
        Each result dict has: text, source, chunk_index, distance.
        """
        count = self.collection.count()
        if count == 0:
            return []

        query_embedding = self._embed([query], input_type="query")[0]
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )

        if not results["ids"][0]:
            return []

        return [
            {
                "text": results["documents"][0][i],
                "source": results["metadatas"][0][i]["source"],
                "chunk_index": results["metadatas"][0][i]["chunk_index"],
                "distance": results["distances"][0][i],
            }
            for i in range(len(results["ids"][0]))
        ]

    def is_indexed(self) -> bool:
        return self.collection.count() > 0
