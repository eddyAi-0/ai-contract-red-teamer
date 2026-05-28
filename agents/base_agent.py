import json
import os
import re
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

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


class BaseAgent:
    """
    Foundation for all specialized agents.
    Each subclass provides its own system_prompt; this class owns the API call.
    """

    def __init__(self, system_prompt: str, model: str = "claude-sonnet-4-5"):
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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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

            # Strip markdown code fences the model may add despite instructions
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                raw = raw.strip()

            # Remove ASCII control characters (except \n, \t, \r) that break JSON parsing
            raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)

            try:
                return json.loads(raw)
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
