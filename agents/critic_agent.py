import json
import re

from agents.base_agent import BaseAgent

_SYSTEM_PROMPT = """You are a critical legal reviewer tasked with quality-checking contract \
analysis findings produced by other AI agents.

Your responsibilities:
1. For every finding that contains a "legal_citations" field, call verify_citation for each \
   cited excerpt.
   - Remove any citation whose verify_citation result is {"verified": false}.
   - If ALL citations in a finding are unverified AND the finding has no independent textual \
     support from the contract itself, discard the entire finding.
2. For findings without "legal_citations", assess whether the claim is grounded in the contract \
   text. You may call search_legal_corpus to look up supporting references.
3. Return ONLY the verified, grounded findings as a JSON array — no wrapping object, no markdown.

Be rigorous but fair: keep well-supported findings even when they lack citations. \
Only discard findings that are entirely fabricated or wholly unsupported."""

_JSON_ARRAY_INSTRUCTION = (
    "\n\nRespond ONLY with a valid JSON array. "
    "No markdown, no code fences, no preamble. "
    "Start your response with [ and end with ]."
)


class CriticAgent(BaseAgent):
    """Verifies citations and discards unsupported findings from a merged findings list."""

    def __init__(self):
        super().__init__(system_prompt=_SYSTEM_PROMPT)

    def critique_findings(self, findings: list[dict], max_turns: int = 4) -> list[dict]:
        """
        Run the agentic review loop on a merged findings list.
        Returns a (potentially shorter) list of verified findings.
        Falls back to the original list unchanged if the loop fails to produce
        parseable output.
        """
        if not findings:
            return findings

        tools = self._define_tools()
        messages: list[dict] = [
            {
                "role": "user",
                "content": (
                    "Review the following contract analysis findings for accuracy. "
                    "Use verify_citation for every entry in 'legal_citations' before keeping it. "
                    "Discard findings whose citations are all unverified and have no independent "
                    "textual support from the contract text."
                    + _JSON_ARRAY_INSTRUCTION
                    + f"\n\nFindings to review:\n{json.dumps(findings, indent=2)}"
                ),
            }
        ]

        for _ in range(max_turns):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=self.system_prompt,
                tools=tools,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                text_block = next(
                    (b for b in response.content if getattr(b, "type", None) == "text"),
                    None,
                )
                if text_block:
                    try:
                        return self._parse_findings_list(text_block.text)
                    except (ValueError, json.JSONDecodeError):
                        pass
                break

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if getattr(block, "type", None) == "tool_use":
                        result = self._execute_tool(block.name, block.input)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result),
                            }
                        )
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        # Return original findings if the loop fails to produce a valid response
        return findings

    def _parse_findings_list(self, raw: str) -> list[dict]:
        """Clean a raw model response and parse it as a JSON array."""
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            raw = raw.strip()
        raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
        result = json.loads(raw)
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "findings" in result:
            return result["findings"]
        raise ValueError(f"Expected JSON array, got {type(result).__name__}")
