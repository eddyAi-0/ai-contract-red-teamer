import json
import pytest
from unittest.mock import MagicMock, patch

from agents.base_agent import BaseAgent
from agents.legal_agent import LegalAgent
from agents.financial_agent import FinancialAgent
from agents.practical_agent import PracticalAgent
from orchestrator.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(text: str) -> MagicMock:
    m = MagicMock()
    m.content = [MagicMock(text=text)]
    return m


def _agent_payload(agent_type: str, risk_score: int, severity: str = "high") -> dict:
    return {
        "agent_type": agent_type,
        "risk_score": risk_score,
        "findings": [
            {
                "severity": severity,
                "title": f"{agent_type} finding",
                "description": "desc",
                "clause_reference": "clause text",
                "recommendation": "rec",
            }
        ],
        "summary": f"{agent_type} summary",
    }


# ---------------------------------------------------------------------------
# BaseAgent
# ---------------------------------------------------------------------------

class TestBaseAgent:
    def test_stores_system_prompt(self):
        with patch("agents.base_agent.Anthropic"):
            agent = BaseAgent(system_prompt="You are a legal expert.")
        assert agent.system_prompt == "You are a legal expert."

    def test_default_model(self):
        with patch("agents.base_agent.Anthropic"):
            agent = BaseAgent(system_prompt="test")
        assert agent.model == "claude-sonnet-4-5"

    def test_analyze_returns_text(self):
        with patch("agents.base_agent.Anthropic") as MockAnthropicClass:
            mock_client = MagicMock()
            MockAnthropicClass.return_value = mock_client
            mock_client.messages.create.return_value = _mock_response("Analysis result")
            agent = BaseAgent(system_prompt="test")

        result = agent.analyze("contract text")
        assert result == "Analysis result"

    def test_analyze_structured_parses_json(self):
        payload = _agent_payload("legal", 7)
        with patch("agents.base_agent.Anthropic") as MockAnthropicClass:
            mock_client = MagicMock()
            MockAnthropicClass.return_value = mock_client
            mock_client.messages.create.return_value = _mock_response(json.dumps(payload))
            agent = BaseAgent(system_prompt="test")

        result = agent.analyze_structured("contract text")
        assert result["risk_score"] == 7
        assert result["agent_type"] == "legal"

    def test_analyze_structured_strips_markdown_fences(self):
        payload = json.dumps({"risk_score": 5, "findings": []})
        fenced = f"```json\n{payload}\n```"
        with patch("agents.base_agent.Anthropic") as MockAnthropicClass:
            mock_client = MagicMock()
            MockAnthropicClass.return_value = mock_client
            mock_client.messages.create.return_value = _mock_response(fenced)
            agent = BaseAgent(system_prompt="test")

        result = agent.analyze_structured("contract text")
        assert result["risk_score"] == 5

    def test_analyze_structured_retries_on_bad_json(self):
        good_payload = json.dumps({"risk_score": 3, "findings": []})
        with patch("agents.base_agent.Anthropic") as MockAnthropicClass:
            mock_client = MagicMock()
            MockAnthropicClass.return_value = mock_client
            mock_client.messages.create.side_effect = [
                _mock_response("not valid json {{{{"),
                _mock_response(good_payload),
            ]
            agent = BaseAgent(system_prompt="test")

        result = agent.analyze_structured("contract text")
        assert result["risk_score"] == 3
        assert mock_client.messages.create.call_count == 2

    def test_analyze_structured_raises_after_two_failures(self):
        with patch("agents.base_agent.Anthropic") as MockAnthropicClass:
            mock_client = MagicMock()
            MockAnthropicClass.return_value = mock_client
            mock_client.messages.create.return_value = _mock_response("still not json")
            agent = BaseAgent(system_prompt="test")

        with pytest.raises(ValueError, match="Failed to parse JSON"):
            agent.analyze_structured("contract text")


# ---------------------------------------------------------------------------
# LegalAgent
# ---------------------------------------------------------------------------

class TestLegalAgent:
    def test_system_prompt_covers_gdpr(self):
        with patch("agents.base_agent.Anthropic"):
            agent = LegalAgent()
        assert "GDPR" in agent.system_prompt or "gdpr" in agent.system_prompt.lower()

    def test_system_prompt_covers_jurisdiction(self):
        with patch("agents.base_agent.Anthropic"):
            agent = LegalAgent()
        assert "jurisdiction" in agent.system_prompt.lower()

    def test_analyze_structured_returns_legal_type(self):
        payload = _agent_payload("legal", 6)
        with patch("agents.base_agent.Anthropic") as MockAnthropicClass:
            mock_client = MagicMock()
            MockAnthropicClass.return_value = mock_client
            mock_client.messages.create.return_value = _mock_response(json.dumps(payload))
            agent = LegalAgent()

        result = agent.analyze_structured("contract")
        assert result["agent_type"] == "legal"
        assert 0 <= result["risk_score"] <= 10


# ---------------------------------------------------------------------------
# FinancialAgent
# ---------------------------------------------------------------------------

class TestFinancialAgent:
    def test_system_prompt_covers_financial_keywords(self):
        with patch("agents.base_agent.Anthropic"):
            agent = FinancialAgent()
        prompt = agent.system_prompt.lower()
        assert any(kw in prompt for kw in ["cost", "payment", "penalty", "renewal", "fee"])

    def test_analyze_structured_returns_financial_type(self):
        payload = _agent_payload("financial", 4)
        with patch("agents.base_agent.Anthropic") as MockAnthropicClass:
            mock_client = MagicMock()
            MockAnthropicClass.return_value = mock_client
            mock_client.messages.create.return_value = _mock_response(json.dumps(payload))
            agent = FinancialAgent()

        result = agent.analyze_structured("contract")
        assert result["agent_type"] == "financial"


# ---------------------------------------------------------------------------
# PracticalAgent
# ---------------------------------------------------------------------------

class TestPracticalAgent:
    def test_system_prompt_covers_practical_keywords(self):
        with patch("agents.base_agent.Anthropic"):
            agent = PracticalAgent()
        prompt = agent.system_prompt.lower()
        assert any(kw in prompt for kw in ["obligation", "deadline", "exit", "termination"])

    def test_analyze_structured_returns_practical_type(self):
        payload = _agent_payload("practical", 5)
        with patch("agents.base_agent.Anthropic") as MockAnthropicClass:
            mock_client = MagicMock()
            MockAnthropicClass.return_value = mock_client
            mock_client.messages.create.return_value = _mock_response(json.dumps(payload))
            agent = PracticalAgent()

        result = agent.analyze_structured("contract")
        assert result["agent_type"] == "practical"


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _make_orchestrator(legal_score=7, financial_score=5, practical_score=4) -> Orchestrator:
    """Build an Orchestrator with all external calls mocked out."""
    with patch("agents.base_agent.Anthropic"), patch("orchestrator.orchestrator.Anthropic"):
        orch = Orchestrator()

    orch.legal_agent = MagicMock()
    orch.legal_agent.analyze_structured.return_value = _agent_payload("legal", legal_score, "high")

    orch.financial_agent = MagicMock()
    orch.financial_agent.analyze_structured.return_value = _agent_payload(
        "financial", financial_score, "critical"
    )

    orch.practical_agent = MagicMock()
    orch.practical_agent.analyze_structured.return_value = _agent_payload(
        "practical", practical_score, "low"
    )

    orch.client = MagicMock()
    orch.client.messages.create.return_value = _mock_response("Executive summary text.")
    return orch


class TestOrchestrator:
    def test_calls_all_three_agents(self):
        orch = _make_orchestrator()
        orch.analyze("contract")
        orch.legal_agent.analyze_structured.assert_called_once_with("contract")
        orch.financial_agent.analyze_structured.assert_called_once_with("contract")
        orch.practical_agent.analyze_structured.assert_called_once_with("contract")

    def test_report_has_expected_keys(self):
        orch = _make_orchestrator()
        result = orch.analyze("contract")
        for key in (
            "overall_risk_score",
            "risk_label",
            "total_findings",
            "findings_count",
            "agent_scores",
            "agent_summaries",
            "executive_summary",
        ):
            assert key in result, f"Missing key: {key}"

    def test_weighted_score_calculation(self):
        # legal=8 * 0.4 + financial=4 * 0.35 + practical=2 * 0.25 = 3.2 + 1.4 + 0.5 = 5.1
        orch = _make_orchestrator(legal_score=8, financial_score=4, practical_score=2)
        result = orch.analyze("contract")
        assert result["overall_risk_score"] == pytest.approx(5.1, abs=0.05)

    def test_findings_sorted_critical_first(self):
        orch = _make_orchestrator()
        result = orch.analyze("contract")
        severities = [f["severity"] for f in result["total_findings"]]
        # financial=critical, legal=high, practical=low
        assert severities == ["critical", "high", "low"]

    def test_findings_tagged_with_source_agent(self):
        orch = _make_orchestrator()
        result = orch.analyze("contract")
        sources = {f["source_agent"] for f in result["total_findings"]}
        assert sources == {"legal", "financial", "practical"}

    def test_risk_label_critical_at_high_scores(self):
        orch = _make_orchestrator(legal_score=9, financial_score=9, practical_score=9)
        result = orch.analyze("contract")
        assert result["risk_label"] == "CRITICAL"

    def test_risk_label_minimal_at_low_scores(self):
        orch = _make_orchestrator(legal_score=1, financial_score=1, practical_score=1)
        result = orch.analyze("contract")
        assert result["risk_label"] == "MINIMAL"

    def test_executive_summary_from_claude(self):
        orch = _make_orchestrator()
        result = orch.analyze("contract")
        assert result["executive_summary"] == "Executive summary text."

    def test_findings_count_matches_list_length(self):
        orch = _make_orchestrator()
        result = orch.analyze("contract")
        assert result["findings_count"] == len(result["total_findings"])


# ---------------------------------------------------------------------------
# Orchestrator + VectorStore integration
# ---------------------------------------------------------------------------

class TestOrchestratorRAG:
    def test_vectorstore_injected_into_all_agents(self):
        mock_vs = MagicMock()
        with patch("agents.base_agent.Anthropic"), patch("orchestrator.orchestrator.Anthropic"):
            orch = Orchestrator(vectorstore=mock_vs)

        assert orch.legal_agent.vectorstore is mock_vs
        assert orch.financial_agent.vectorstore is mock_vs
        assert orch.practical_agent.vectorstore is mock_vs

    def test_analyze_calls_rag_method_when_vectorstore_provided(self):
        mock_vs = MagicMock()
        with patch("agents.base_agent.Anthropic"), patch("orchestrator.orchestrator.Anthropic"):
            orch = Orchestrator(vectorstore=mock_vs)

        orch.legal_agent = MagicMock()
        orch.legal_agent.analyze_structured_with_rag.return_value = _agent_payload("legal", 6)
        orch.financial_agent = MagicMock()
        orch.financial_agent.analyze_structured_with_rag.return_value = _agent_payload("financial", 4)
        orch.practical_agent = MagicMock()
        orch.practical_agent.analyze_structured_with_rag.return_value = _agent_payload("practical", 3)
        orch.client = MagicMock()
        orch.client.messages.create.return_value = _mock_response("Summary.")

        orch.analyze("contract text")

        orch.legal_agent.analyze_structured_with_rag.assert_called_once_with("contract text")
        orch.financial_agent.analyze_structured_with_rag.assert_called_once_with("contract text")
        orch.practical_agent.analyze_structured_with_rag.assert_called_once_with("contract text")

    def test_analyze_uses_plain_structured_when_no_vectorstore(self):
        with patch("agents.base_agent.Anthropic"), patch("orchestrator.orchestrator.Anthropic"):
            orch = Orchestrator()  # no vectorstore

        orch.legal_agent = MagicMock()
        orch.legal_agent.analyze_structured.return_value = _agent_payload("legal", 5)
        orch.financial_agent = MagicMock()
        orch.financial_agent.analyze_structured.return_value = _agent_payload("financial", 3)
        orch.practical_agent = MagicMock()
        orch.practical_agent.analyze_structured.return_value = _agent_payload("practical", 2)
        orch.client = MagicMock()
        orch.client.messages.create.return_value = _mock_response("Summary.")

        orch.analyze("contract text")

        orch.legal_agent.analyze_structured.assert_called_once_with("contract text")
        orch.legal_agent.analyze_structured_with_rag.assert_not_called()
