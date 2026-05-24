"""
Indexing script: parse all PDFs in rag/documents/ and store them in ChromaDB.

Usage (from project root):
    python -m rag.indexer
"""
from pathlib import Path

from rag.vectorstore import VectorStore


def run() -> None:
    docs_dir = Path(__file__).parent / "documents"
    pdfs = sorted(docs_dir.glob("*.pdf"))

    if not pdfs:
        print("No PDFs found in rag/documents/ — add documents and re-run.")
        return

    vs = VectorStore()

    for pdf_path in pdfs:
        print(f"Indexing {pdf_path.name}...", end=" ", flush=True)
        count = vs.index_pdf(str(pdf_path), pdf_path.name)
        if count == 0:
            print("already indexed, skipped.")
        else:
            print(f"{count} chunks added.")

    print(f"\nDone. Collection size: {vs.collection.count()} chunks.")


if __name__ == "__main__":
    run()
