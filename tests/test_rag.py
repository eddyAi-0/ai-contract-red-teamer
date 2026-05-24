import json
import pytest
from unittest.mock import MagicMock, patch, call

from rag.vectorstore import VectorStore, split_text
from agents.base_agent import BaseAgent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def vs_mocks():
    """Provide a VectorStore with chromadb and voyageai fully mocked out."""
    mock_collection = MagicMock()
    mock_chroma_client = MagicMock()
    mock_chroma_client.get_or_create_collection.return_value = mock_collection

    mock_embed_result = MagicMock()
    mock_embed_result.embeddings = [[0.1, 0.2, 0.3]]
    mock_voyage_client = MagicMock()
    mock_voyage_client.embed.return_value = mock_embed_result

    with (
        patch("rag.vectorstore.chromadb.PersistentClient", return_value=mock_chroma_client),
        patch("rag.vectorstore.voyageai.Client", return_value=mock_voyage_client),
    ):
        vs = VectorStore(chroma_dir="/tmp/test_chroma")
        yield vs, mock_collection, mock_voyage_client


# ---------------------------------------------------------------------------
# split_text (pure function — no mocks needed)
# ---------------------------------------------------------------------------

class TestSplitText:
    def test_empty_string_returns_empty_list(self):
        assert split_text("") == []

    def test_short_text_returns_single_chunk(self):
        result = split_text("Hello world.")
        assert result == ["Hello world."]

    def test_text_exactly_chunk_size_returns_single_chunk(self):
        text = "a" * 800
        assert len(split_text(text)) == 1

    def test_long_text_splits_into_multiple_chunks(self):
        text = "word " * 300  # ~1500 chars
        chunks = split_text(text, chunk_size=200, overlap=30)
        assert len(chunks) > 1

    def test_chunks_do_not_exceed_chunk_size_significantly(self):
        text = "sentence one. sentence two. sentence three. " * 50
        chunks = split_text(text, chunk_size=100, overlap=20)
        for chunk in chunks:
            # Allow some slack for the overlap carryover
            assert len(chunk) <= 150, f"Chunk too large: {len(chunk)}"

    def test_prefers_paragraph_boundary(self):
        text = "First paragraph text here.\n\nSecond paragraph goes here now."
        chunks = split_text(text, chunk_size=30, overlap=5)
        # Should split at the \n\n
        assert any("First paragraph" in c for c in chunks)
        assert any("Second paragraph" in c for c in chunks)

    def test_overlap_creates_shared_content_between_chunks(self):
        # With enough overlap, consecutive chunks should share some content
        text = "abcdefghij" * 30  # 300 chars
        chunks = split_text(text, chunk_size=100, overlap=30)
        if len(chunks) >= 2:
            # End of chunk N should overlap with start of chunk N+1
            end_of_first = chunks[0][-20:]
            assert any(end_of_first[:10] in c for c in chunks[1:])

    def test_whitespace_only_returns_empty_list(self):
        assert split_text("   \n\n   ") == []


# ---------------------------------------------------------------------------
# VectorStore.__init__
# ---------------------------------------------------------------------------

class TestVectorStoreInit:
    def test_creates_collection_with_correct_name(self, vs_mocks):
        vs, mock_collection, _ = vs_mocks
        vs.chroma.get_or_create_collection.assert_called_with("legal_documents")

    def test_collection_assigned(self, vs_mocks):
        vs, mock_collection, _ = vs_mocks
        assert vs.collection is mock_collection


# ---------------------------------------------------------------------------
# VectorStore._embed
# ---------------------------------------------------------------------------

class TestVectorStoreEmbed:
    def test_embed_calls_voyage_with_correct_params(self, vs_mocks):
        vs, _, mock_voyage = vs_mocks
        vs._embed(["text one", "text two"], input_type="document")
        mock_voyage.embed.assert_called_once_with(
            ["text one", "text two"], model="voyage-3", input_type="document"
        )

    def test_embed_batches_large_input(self, vs_mocks):
        vs, _, mock_voyage = vs_mocks
        mock_voyage.embed.return_value.embeddings = [[0.1]] * 128

        texts = [f"text {i}" for i in range(300)]
        vs._embed(texts)
        # 300 texts split into batches of 128: ceil(300/128) = 3 calls
        assert mock_voyage.embed.call_count == 3

    def test_embed_query_uses_query_input_type(self, vs_mocks):
        vs, _, mock_voyage = vs_mocks
        vs._embed(["query text"], input_type="query")
        call_kwargs = mock_voyage.embed.call_args.kwargs
        assert call_kwargs["input_type"] == "query"


# ---------------------------------------------------------------------------
# VectorStore.is_indexed
# ---------------------------------------------------------------------------

class TestIsIndexed:
    def test_returns_false_when_empty(self, vs_mocks):
        vs, mock_collection, _ = vs_mocks
        mock_collection.count.return_value = 0
        assert vs.is_indexed() is False

    def test_returns_true_when_has_documents(self, vs_mocks):
        vs, mock_collection, _ = vs_mocks
        mock_collection.count.return_value = 42
        assert vs.is_indexed() is True


# ---------------------------------------------------------------------------
# VectorStore.search
# ---------------------------------------------------------------------------

class TestVectorStoreSearch:
    def test_returns_empty_list_when_collection_empty(self, vs_mocks):
        vs, mock_collection, _ = vs_mocks
        mock_collection.count.return_value = 0
        result = vs.search("some query")
        assert result == []

    def test_returns_formatted_results(self, vs_mocks):
        vs, mock_collection, mock_voyage = vs_mocks
        mock_collection.count.return_value = 5
        mock_voyage.embed.return_value.embeddings = [[0.5, 0.6, 0.7]]
        mock_collection.query.return_value = {
            "ids": [["gdpr.pdf_chunk_0", "gdpr.pdf_chunk_3"]],
            "documents": [["Art. 7 text", "Art. 13 text"]],
            "metadatas": [
                [
                    {"source": "gdpr.pdf", "chunk_index": 0},
                    {"source": "gdpr.pdf", "chunk_index": 3},
                ]
            ],
            "distances": [[0.12, 0.34]],
        }

        results = vs.search("consent clause", top_k=2)

        assert len(results) == 2
        assert results[0]["text"] == "Art. 7 text"
        assert results[0]["source"] == "gdpr.pdf"
        assert results[0]["chunk_index"] == 0
        assert results[0]["distance"] == 0.12

    def test_search_uses_query_input_type_for_embedding(self, vs_mocks):
        vs, mock_collection, mock_voyage = vs_mocks
        mock_collection.count.return_value = 1
        mock_collection.query.return_value = {
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]
        }
        mock_voyage.embed.return_value.embeddings = [[0.1, 0.2]]

        vs.search("my query")

        embed_call = mock_voyage.embed.call_args
        assert embed_call.kwargs.get("input_type") == "query"

    def test_search_caps_n_results_at_collection_size(self, vs_mocks):
        vs, mock_collection, mock_voyage = vs_mocks
        mock_collection.count.return_value = 2  # only 2 docs
        mock_collection.query.return_value = {
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]
        }
        mock_voyage.embed.return_value.embeddings = [[0.1]]

        vs.search("query", top_k=10)  # ask for 10 but only 2 exist

        query_kwargs = mock_collection.query.call_args.kwargs
        assert query_kwargs["n_results"] == 2


# ---------------------------------------------------------------------------
# VectorStore.index_pdf
# ---------------------------------------------------------------------------

class TestIndexPdf:
    def test_skips_already_indexed_source(self, vs_mocks):
        vs, mock_collection, _ = vs_mocks
        mock_collection.get.return_value = {"ids": ["gdpr.pdf_chunk_0"]}

        result = vs.index_pdf("/some/path.pdf", "gdpr.pdf")

        assert result == 0
        mock_collection.add.assert_not_called()

    def test_indexes_new_source_and_returns_chunk_count(self, vs_mocks):
        vs, mock_collection, mock_voyage = vs_mocks
        mock_collection.get.return_value = {"ids": []}
        mock_voyage.embed.return_value.embeddings = [[0.1, 0.2]] * 5

        with patch("rag.vectorstore.extract_text_from_pdf", return_value="word " * 200):
            count = vs.index_pdf("/path/gdpr.pdf", "gdpr.pdf")

        assert count > 0
        mock_collection.add.assert_called_once()

    def test_ids_use_source_name_prefix(self, vs_mocks):
        vs, mock_collection, mock_voyage = vs_mocks
        mock_collection.get.return_value = {"ids": []}
        mock_voyage.embed.return_value.embeddings = [[0.1]] * 3

        with patch(
            "rag.vectorstore.extract_text_from_pdf",
            return_value="A short text.\n\nAnother paragraph.\n\nThird paragraph here.",
        ):
            vs.index_pdf("/path/contract.pdf", "contract.pdf")

        add_kwargs = mock_collection.add.call_args.kwargs
        assert all(id_.startswith("contract.pdf_chunk_") for id_ in add_kwargs["ids"])

    def test_returns_zero_for_empty_pdf(self, vs_mocks):
        vs, mock_collection, _ = vs_mocks
        mock_collection.get.return_value = {"ids": []}

        with patch("rag.vectorstore.extract_text_from_pdf", return_value=""):
            count = vs.index_pdf("/path/empty.pdf", "empty.pdf")

        assert count == 0


# ---------------------------------------------------------------------------
# BaseAgent RAG methods
# ---------------------------------------------------------------------------

def _mock_agent_response(payload: dict) -> MagicMock:
    m = MagicMock()
    m.content = [MagicMock(text=json.dumps(payload))]
    return m


class TestBaseAgentRAG:
    def _make_agent(self, response_payload: dict) -> tuple[BaseAgent, MagicMock]:
        with patch("agents.base_agent.Anthropic") as MockClass:
            mock_client = MagicMock()
            MockClass.return_value = mock_client
            mock_client.messages.create.return_value = _mock_agent_response(response_payload)
            agent = BaseAgent(system_prompt="test")
        return agent, mock_client

    def test_fallback_when_vectorstore_is_none(self):
        payload = {"risk_score": 3, "findings": []}
        agent, mock_client = self._make_agent(payload)
        assert agent.vectorstore is None

        result = agent.analyze_structured_with_rag("contract text")

        assert result["risk_score"] == 3
        mock_client.messages.create.assert_called_once()

    def test_fallback_when_search_returns_empty(self):
        payload = {"risk_score": 3, "findings": []}
        agent, mock_client = self._make_agent(payload)

        mock_vs = MagicMock()
        mock_vs.search.return_value = []
        agent.set_vectorstore(mock_vs)

        agent.analyze_structured_with_rag("contract text")

        # Falls back to plain analyze_structured — no REFERENCE LEGAL TEXT in prompt
        content = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "REFERENCE LEGAL TEXT" not in content

    def test_builds_enriched_prompt_when_chunks_found(self):
        payload = {"risk_score": 7, "findings": []}
        agent, mock_client = self._make_agent(payload)

        mock_vs = MagicMock()
        mock_vs.search.return_value = [
            {"text": "Art. 7 — Conditions for consent", "source": "gdpr.pdf",
             "chunk_index": 3, "distance": 0.1}
        ]
        agent.set_vectorstore(mock_vs)

        agent.analyze_structured_with_rag("my contract text")

        content = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "REFERENCE LEGAL TEXT" in content
        assert "gdpr.pdf" in content
        assert "Art. 7" in content

    def test_vectorstore_queried_with_contract_text(self):
        payload = {"risk_score": 5, "findings": []}
        agent, _ = self._make_agent(payload)

        mock_vs = MagicMock()
        mock_vs.search.return_value = []
        agent.set_vectorstore(mock_vs)

        agent.analyze_structured_with_rag("the actual contract text", top_k=5)

        mock_vs.search.assert_called_once_with("the actual contract text", top_k=5)

    def test_set_vectorstore_assigns_attribute(self):
        with patch("agents.base_agent.Anthropic"):
            agent = BaseAgent(system_prompt="test")
        mock_vs = MagicMock()
        agent.set_vectorstore(mock_vs)
        assert agent.vectorstore is mock_vs
