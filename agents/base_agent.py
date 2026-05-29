import json
import os
import re
from difflib import SequenceMatcher

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# Pinned, dated model version for reproducible runs.
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"

_JSON_INSTRUCTION = (
    "\n\nRespond ONLY with a valid JSON object. "
    "No markdown, no code fences, no preamble. "
    "Start your response with { and end with }."
)
_JSON_STRICT_INSTRUCTION = (
    "\n\nYOUR RESPONSE MUST BE RAW JSON ONLY. "
    "Start immediately with { and end with }. "
    "No markdown, no ```json``` blocks, no text before or after."
)
_AGENTIC_FINISH_INSTRUCTION = (
    "\n\nWhen you have finished your analysis, respond with a valid JSON object only. "
    "No markdown, no code fences. Start with { and end with }. "
    "The JSON must contain: agent_type, risk_score (0-10), findings[], summary."
)


class BaseAgent:
    """
    Foundation for all specialized agents.
    Each subclass provides its own system_prompt; this class owns the API call.
    """

    def __init__(self, system_prompt: str, model: str = DEFAULT_MODEL):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.system_prompt = system_prompt
        self.model = model
        self.vectorstore = None

    def set_vectorstore(self, vs) -> None:
        self.vectorstore = vs

    def analyze(self, text: str) -> str:
        """Send contract text to the model and return the raw analysis string."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"Analyze the following contract text:\n\n{text}",
                }
            ],
        )
        return response.content[0].text

    def analyze_structured(self, text: str) -> dict:
        """Call the model and parse the JSON response, with one retry on parse failure."""
        return self._analyze_json(f"Analyze the following contract text:\n\n{text}")

    def analyze_structured_with_rag(self, text: str, top_k: int = 3) -> dict:
        """
        Like analyze_structured, but enriches the prompt with relevant chunks
        from the vector store when one is available.
        Falls back to analyze_structured if no vectorstore is set or search returns nothing.
        """
        if self.vectorstore is None:
            return self.analyze_structured(text)

        chunks = self.vectorstore.search(text, top_k=top_k)
        if not chunks:
            return self.analyze_structured(text)

        context = self._build_rag_context(chunks)
        user_message = (
            f"Analyze the following contract text:\n\n{text}\n\n"
            f"{context}\n\n"
            "When a finding relates to content in the REFERENCE LEGAL TEXT above, "
            "add a \"legal_citations\" field to that finding: "
            "[{\"source\": \"<filename>\", \"excerpt\": \"<relevant quote from reference>\"}]. "
            "Cite only text that actually appears in REFERENCE LEGAL TEXT."
        )
        return self._analyze_json(user_message)

    def analyze_agentic(self, contract_text: str, max_turns: int = 4) -> dict:
        """
        Agentic analysis loop with tool use.  The model can call search_legal_corpus
        and verify_citation as many times as it needs before emitting the final JSON.

        Output shape is identical to analyze_structured_with_rag so the rest of the
        project can use either method without changes.

        Falls back to analyze_structured_with_rag when max_turns is exhausted or the
        loop produces no parseable output.
        """
        tools = self._define_tools()
        messages: list[dict] = [
            {
                "role": "user",
                "content": (
                    f"Analyze the following contract text:\n\n{contract_text}\n\n"
                    "You have two tools available:\n"
                    "• search_legal_corpus – retrieve relevant regulatory text from the corpus.\n"
                    "• verify_citation – confirm an excerpt actually exists before citing it.\n"
                    "Call verify_citation for EVERY citation you plan to include and omit any "
                    "that cannot be verified."
                    + _AGENTIC_FINISH_INSTRUCTION
                ),
            }
        ]

        response = None
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
                        return self._parse_raw_to_dict(text_block.text)
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
                # Unexpected stop reason (e.g. max_tokens) — fall through to fallback
                break

        # Loop exhausted or produced unparseable output: use single-pass RAG as fallback
        return self.analyze_structured_with_rag(contract_text)

    # ------------------------------------------------------------------
    # Tool definitions and execution
    # ------------------------------------------------------------------

    def _define_tools(self) -> list[dict]:
        return [
            {
                "name": "search_legal_corpus",
                "description": (
                    "Search the legal corpus for normative references, regulatory text, "
                    "or case law relevant to a topic. Returns matching text excerpts with "
                    "source attribution."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural-language query to find relevant legal text.",
                        }
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "verify_citation",
                "description": (
                    "Verify that a specific text excerpt actually exists in the legal corpus. "
                    "Returns {\"verified\": true} if the excerpt is found verbatim or near-verbatim, "
                    "{\"verified\": false} otherwise. "
                    "Always call this before including a citation in findings."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "excerpt": {
                            "type": "string",
                            "description": "The exact or near-exact text excerpt to look up.",
                        }
                    },
                    "required": ["excerpt"],
                },
            },
        ]

    def _execute_tool(self, name: str, inputs: dict) -> dict:
        if name == "search_legal_corpus":
            if self.vectorstore is None:
                return {"results": []}
            results = self.vectorstore.search(inputs.get("query", ""), top_k=3)
            return {
                "results": [
                    {"source": r["source"], "text": r["text"]} for r in results
                ]
            }
        if name == "verify_citation":
            return self._verify_citation(inputs.get("excerpt", ""))
        return {"error": f"Unknown tool: {name}"}

    def _verify_citation(self, excerpt: str) -> dict:
        """
        Return {"verified": True} if excerpt is found in a retrieved corpus chunk,
        {"verified": False} otherwise.

        Two-stage match against each candidate chunk (whitespace/case normalised):
        1. Fast-path: exact substring containment.
        2. Fuzzy: slide a window over the chunk the same word-length as the excerpt
           and take the best SequenceMatcher ratio across those windows. Comparing
           against same-length windows (rather than the whole chunk) is what makes
           the fuzzy stage work: a short excerpt vs. an 800-char chunk would always
           score near zero, so the threshold could never be met. The 0.85 threshold
           rejects fabrications while tolerating minor paraphrasing / punctuation.
        """
        if self.vectorstore is None:
            return {"verified": False}
        normalised_excerpt = " ".join(excerpt.lower().split())
        if not normalised_excerpt:
            return {"verified": False}

        candidates = self.vectorstore.search(excerpt, top_k=3)
        for candidate in candidates:
            normalised_text = " ".join(candidate["text"].lower().split())
            if normalised_excerpt in normalised_text:
                return {"verified": True}
            if self._best_window_ratio(normalised_excerpt, normalised_text) >= 0.85:
                return {"verified": True}
        return {"verified": False}

    @staticmethod
    def _best_window_ratio(excerpt: str, text: str) -> float:
        """
        Best SequenceMatcher ratio between `excerpt` and every word-window of `text`
        whose length (in words) equals the excerpt's. Both inputs are pre-normalised.
        If the text is shorter than the excerpt window, compare against the whole text.
        """
        excerpt_words = excerpt.split()
        text_words = text.split()
        window = len(excerpt_words)
        if window == 0 or len(text_words) <= window:
            return SequenceMatcher(None, excerpt, text).ratio()

        best = 0.0
        for start in range(len(text_words) - window + 1):
            candidate = " ".join(text_words[start:start + window])
            ratio = SequenceMatcher(None, excerpt, candidate).ratio()
            if ratio > best:
                best = ratio
                if best == 1.0:
                    break
        return best

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_raw_to_dict(self, raw: str) -> dict:
        """Strip markdown fences and control characters, then JSON-parse."""
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            raw = raw.strip()
        raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
        return json.loads(raw)

    def _analyze_json(self, user_message: str) -> dict:
        """
        Send user_message to the model and parse the JSON response.
        Retries once with a stricter instruction on parse failure.
        Raises ValueError if both attempts fail.
        """
        prompts = [
            user_message + _JSON_INSTRUCTION,
            user_message + _JSON_STRICT_INSTRUCTION,
        ]

        for attempt, msg in enumerate(prompts):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=self.system_prompt,
                messages=[{"role": "user", "content": msg}],
            )
            raw = response.content[0].text.strip()

            try:
                return self._parse_raw_to_dict(raw)
            except json.JSONDecodeError:
                if attempt == len(prompts) - 1:
                    raise ValueError(
                        f"Failed to parse JSON after {len(prompts)} attempts. "
                        f"Last raw response:\n{raw}"
                    )

        raise ValueError("Unexpected exit from _analyze_json retry loop")

    @staticmethod
    def _build_rag_context(chunks: list[dict]) -> str:
        lines = ["---", "REFERENCE LEGAL TEXT (retrieved from normative database):"]
        for chunk in chunks:
            lines.append(
                f"\n[Source: {chunk['source']} | Chunk {chunk['chunk_index']}]\n"
                f"\"{chunk['text']}\""
            )
        lines.append("---")
        return "\n".join(lines)
