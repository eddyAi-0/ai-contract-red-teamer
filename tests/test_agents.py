import json
import pytest
from unittest.mock import MagicMock, patch

from agents.base_agent import BaseAgent
from agents.legal_agent import LegalAgent
from agents.financial_agent import FinancialAgent
from agents.practical_agent import PracticalAgent
from agents.critic_agent import CriticAgent
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


def _mock_end_turn_response(text: str) -> MagicMock:
    """Simulate a model response that terminates the agentic loop."""
    m = MagicMock()
    m.stop_reason = "end_turn"
    block = MagicMock()
    block.type = "text"
    block.text = text
    m.content = [block]
    return m


def _mock_tool_use_response(tool_name: str, tool_id: str, tool_input: dict) -> MagicMock:
    """Simulate a model response that requests a tool call."""
    m = MagicMock()
    m.stop_reason = "tool_use"
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = tool_name
    block.input = tool_input
    m.content = [block]
    return m


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
# Agentic loop — BaseAgent
# ---------------------------------------------------------------------------

class TestBaseAgentAgentic:
    def _make_agent(self) -> tuple[BaseAgent, MagicMock]:
        with patch("agents.base_agent.Anthropic") as MockClass:
            mock_client = MagicMock()
            MockClass.return_value = mock_client
            agent = BaseAgent(system_prompt="test")
        return agent, mock_client

    def test_agentic_loop_terminates_at_first_turn(self):
        """Model replies with end_turn immediately — single API call, correct output."""
        payload = _agent_payload("legal", 7)
        agent, mock_client = self._make_agent()
        mock_client.messages.create.return_value = _mock_end_turn_response(
            json.dumps(payload)
        )

        result = agent.analyze_agentic("contract text")

        assert result["agent_type"] == "legal"
        assert result["risk_score"] == 7
        assert mock_client.messages.create.call_count == 1

    def test_agentic_loop_with_one_tool_call(self):
        """Model calls search_legal_corpus once, then returns final JSON."""
        payload = _agent_payload("financial", 5)
        agent, mock_client = self._make_agent()

        mock_vs = MagicMock()
        mock_vs.search.return_value = [
            {"text": "Art. 7 consent", "source": "gdpr.pdf",
             "chunk_index": 0, "distance": 0.1}
        ]
        agent.set_vectorstore(mock_vs)

        mock_client.messages.create.side_effect = [
            _mock_tool_use_response(
                "search_legal_corpus", "tool_abc", {"query": "penalty clauses"}
            ),
            _mock_end_turn_response(json.dumps(payload)),
        ]

        result = agent.analyze_agentic("contract text")

        assert result["risk_score"] == 5
        assert mock_client.messages.create.call_count == 2
        # Second call should include a tool_result user message
        second_call_messages = mock_client.messages.create.call_args_list[1][1]["messages"]
        assert any(
            isinstance(m.get("content"), list)
            and m["content"][0].get("type") == "tool_result"
            for m in second_call_messages
        )

    def test_verify_citation_returns_false_for_unmatched_excerpt(self):
        """An excerpt unrelated to any corpus chunk produces verified=False."""
        agent, _ = self._make_agent()

        mock_vs = MagicMock()
        mock_vs.search.return_value = [
            {"text": "Article 7 conditions for consent under GDPR",
             "source": "gdpr.pdf", "chunk_index": 0, "distance": 0.5}
        ]
        agent.set_vectorstore(mock_vs)

        result = agent._verify_citation(
            "completely fabricated text that does not match anything in corpus"
        )
        assert result == {"verified": False}

    def test_verify_citation_returns_true_for_matched_excerpt(self):
        """An excerpt that appears verbatim in a corpus chunk produces verified=True."""
        agent, _ = self._make_agent()

        mock_vs = MagicMock()
        mock_vs.search.return_value = [
            {"text": "Article 7 conditions for consent under GDPR",
             "source": "gdpr.pdf", "chunk_index": 0, "distance": 0.05}
        ]
        agent.set_vectorstore(mock_vs)

        result = agent._verify_citation("Article 7 conditions for consent under GDPR")
        assert result == {"verified": True}

    def test_agentic_loop_reaches_max_turns_without_crash(self):
        """When the model never stops, the loop exhausts and falls back to RAG."""
        agent, mock_client = self._make_agent()
        # Always respond with a tool_use to force loop exhaustion
        mock_client.messages.create.return_value = _mock_tool_use_response(
            "search_legal_corpus", "tool_x", {"query": "query"}
        )
        fallback_payload = _agent_payload("legal", 3)
        agent.analyze_structured_with_rag = MagicMock(return_value=fallback_payload)

        result = agent.analyze_agentic("contract text", max_turns=2)

        assert result == fallback_payload
        assert mock_client.messages.create.call_count == 2
        agent.analyze_structured_with_rag.assert_called_once_with("contract text")


# ---------------------------------------------------------------------------
# CriticAgent
# ---------------------------------------------------------------------------

class TestCriticAgent:
    def _make_critic(self) -> tuple[CriticAgent, MagicMock]:
        with patch("agents.base_agent.Anthropic") as MockClass:
            mock_client = MagicMock()
            MockClass.return_value = mock_client
            agent = CriticAgent()
        return agent, mock_client

    def test_system_prompt_covers_verification_keywords(self):
        with patch("agents.base_agent.Anthropic"):
            agent = CriticAgent()
        prompt = agent.system_prompt.lower()
        assert any(kw in prompt for kw in ["verify", "citation", "discard", "unverified"])

    def test_critique_findings_returns_empty_list_unchanged(self):
        """Empty input bypasses the API call entirely."""
        critic, mock_client = self._make_critic()
        result = critic.critique_findings([])
        assert result == []
        mock_client.messages.create.assert_not_called()

    def test_critique_findings_terminates_at_first_turn(self):
        """Model returns cleaned findings immediately (no tool calls)."""
        critic, mock_client = self._make_critic()
        cleaned = [{"title": "verified finding", "severity": "high"}]
        mock_client.messages.create.return_value = _mock_end_turn_response(
            json.dumps(cleaned)
        )

        result = critic.critique_findings([{"title": "original", "severity": "high"}])

        assert result == cleaned
        assert mock_client.messages.create.call_count == 1

    def test_critique_findings_with_one_tool_call(self):
        """Model calls verify_citation once, then returns cleaned list."""
        critic, mock_client = self._make_critic()

        mock_vs = MagicMock()
        mock_vs.search.return_value = [
            {"text": "Article 7 consent", "source": "gdpr.pdf",
             "chunk_index": 0, "distance": 0.1}
        ]
        critic.set_vectorstore(mock_vs)

        cleaned = [{"title": "verified finding", "severity": "medium"}]
        mock_client.messages.create.side_effect = [
            _mock_tool_use_response(
                "verify_citation", "tool_v1",
                {"excerpt": "Article 7 consent"}
            ),
            _mock_end_turn_response(json.dumps(cleaned)),
        ]

        result = critic.critique_findings(
            [{"title": "original", "severity": "medium",
              "legal_citations": [{"source": "gdpr.pdf", "excerpt": "Article 7 consent"}]}]
        )

        assert result == cleaned
        assert mock_client.messages.create.call_count == 2

    def test_critique_findings_falls_back_on_max_turns(self):
        """If the loop exhausts without a final JSON, original findings are returned."""
        original = [{"title": "finding", "severity": "low"}]
        critic, mock_client = self._make_critic()
        mock_client.messages.create.return_value = _mock_tool_use_response(
            "verify_citation", "tool_v2", {"excerpt": "x"}
        )

        result = critic.critique_findings(original, max_turns=2)

        assert result == original
        assert mock_client.messages.create.call_count == 2


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _make_orchestrator(legal_score=7, financial_score=5, practical_score=4) -> Orchestrator:
    """Build an Orchestrator with all external calls mocked out."""
    with patch("agents.base_agent.Anthropic"), patch("orchestrator.orchestrator.Anthropic"):
        orch = Orchestrator()

    orch.legal_agent = MagicMock()
    orch.legal_agent.analyze_agentic.return_value = _agent_payload("legal", legal_score, "high")

    orch.financial_agent = MagicMock()
    orch.financial_agent.analyze_agentic.return_value = _agent_payload(
        "financial", financial_score, "critical"
    )

    orch.practical_agent = MagicMock()
    orch.practical_agent.analyze_agentic.return_value = _agent_payload(
        "practical", practical_score, "low"
    )

    # Critic: no vectorstore → _critique_findings is a pass-through
    orch.critic_agent = MagicMock()
    orch.critic_agent.vectorstore = None

    orch.client = MagicMock()
    orch.client.messages.create.return_value = _mock_response("Executive summary text.")
    return orch


class TestOrchestrator:
    def test_calls_all_three_agents(self):
        orch = _make_orchestrator()
        orch.analyze("contract")
        orch.legal_agent.analyze_agentic.assert_called_once_with("contract")
        orch.financial_agent.analyze_agentic.assert_called_once_with("contract")
        orch.practical_agent.analyze_agentic.assert_called_once_with("contract")

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

    def test_critique_findings_called_after_merge(self):
        """_critique_findings must receive the merged findings and its output reaches report."""
        orch = _make_orchestrator()
        reduced = [{"title": "only surviving finding", "severity": "high",
                    "source_agent": "legal"}]
        # Attach a real vectorstore so _critique_findings actually calls the critic
        mock_vs = MagicMock()
        orch.critic_agent.vectorstore = mock_vs
        orch.critic_agent.critique_findings.return_value = reduced

        result = orch.analyze("contract")

        orch.critic_agent.critique_findings.assert_called_once()
        assert result["total_findings"] == reduced
        assert result["findings_count"] == 1

    def test_critique_skipped_when_no_vectorstore(self):
        """Without a corpus, _critique_findings is a no-op."""
        orch = _make_orchestrator()
        # critic_agent.vectorstore is already None in _make_orchestrator
        result = orch.analyze("contract")
        orch.critic_agent.critique_findings.assert_not_called()
        assert result["findings_count"] == 3  # all three agent findings retained


# ---------------------------------------------------------------------------
# Orchestrator + VectorStore integration
# ---------------------------------------------------------------------------

class TestOrchestratorRAG:
    def test_vectorstore_injected_into_all_agents_including_critic(self):
        mock_vs = MagicMock()
        with patch("agents.base_agent.Anthropic"), patch("orchestrator.orchestrator.Anthropic"):
            orch = Orchestrator(vectorstore=mock_vs)

        assert orch.legal_agent.vectorstore is mock_vs
        assert orch.financial_agent.vectorstore is mock_vs
        assert orch.practical_agent.vectorstore is mock_vs
        assert orch.critic_agent.vectorstore is mock_vs

    def test_analyze_calls_agentic_method_with_vectorstore(self):
        mock_vs = MagicMock()
        with patch("agents.base_agent.Anthropic"), patch("orchestrator.orchestrator.Anthropic"):
            orch = Orchestrator(vectorstore=mock_vs)

        orch.legal_agent = MagicMock()
        orch.legal_agent.analyze_agentic.return_value = _agent_payload("legal", 6)
        orch.financial_agent = MagicMock()
        orch.financial_agent.analyze_agentic.return_value = _agent_payload("financial", 4)
        orch.practical_agent = MagicMock()
        orch.practical_agent.analyze_agentic.return_value = _agent_payload("practical", 3)
        orch.critic_agent = MagicMock()
        orch.critic_agent.vectorstore = None  # skip critique in this test
        orch.client = MagicMock()
        orch.client.messages.create.return_value = _mock_response("Summary.")

        orch.analyze("contract text")

        orch.legal_agent.analyze_agentic.assert_called_once_with("contract text")
        orch.financial_agent.analyze_agentic.assert_called_once_with("contract text")
        orch.practical_agent.analyze_agentic.assert_called_once_with("contract text")

    def test_analyze_calls_agentic_without_vectorstore(self):
        """analyze_agentic is used regardless of whether a vectorstore is present."""
        with patch("agents.base_agent.Anthropic"), patch("orchestrator.orchestrator.Anthropic"):
            orch = Orchestrator()  # no vectorstore

        orch.legal_agent = MagicMock()
        orch.legal_agent.analyze_agentic.return_value = _agent_payload("legal", 5)
        orch.financial_agent = MagicMock()
        orch.financial_agent.analyze_agentic.return_value = _agent_payload("financial", 3)
        orch.practical_agent = MagicMock()
        orch.practical_agent.analyze_agentic.return_value = _agent_payload("practical", 2)
        orch.critic_agent = MagicMock()
        orch.critic_agent.vectorstore = None
        orch.client = MagicMock()
        orch.client.messages.create.return_value = _mock_response("Summary.")

        orch.analyze("contract text")

        orch.legal_agent.analyze_agentic.assert_called_once_with("contract text")
        # Old single-pass methods should NOT be called directly by the orchestrator
        orch.legal_agent.analyze_structured.assert_not_called()
        orch.legal_agent.analyze_structured_with_rag.assert_not_called()
