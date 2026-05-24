import pytest
from unittest.mock import MagicMock, patch
from agents.base_agent import BaseAgent


class TestBaseAgent:
    def test_init_stores_system_prompt(self):
        with patch("agents.base_agent.Anthropic"):
            agent = BaseAgent(system_prompt="You are a legal expert.")
            assert agent.system_prompt == "You are a legal expert."

    def test_init_default_model(self):
        with patch("agents.base_agent.Anthropic"):
            agent = BaseAgent(system_prompt="test")
            assert agent.model == "claude-sonnet-4-5"

    def test_analyze_returns_text(self):
        with patch("agents.base_agent.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create.return_value.content = [
                MagicMock(text="Analysis result")
            ]

            agent = BaseAgent(system_prompt="You are a legal expert.")
            result = agent.analyze("Sample contract text")

            assert result == "Analysis result"
            mock_client.messages.create.assert_called_once()
