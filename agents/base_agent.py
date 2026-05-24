import json
import os
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
        """
        Call the model and parse the JSON response.
        Retries once with a stricter prompt if the first response is not valid JSON.
        Raises ValueError if both attempts fail.
        """
        prompts = [
            f"Analyze the following contract text:\n\n{text}{_JSON_INSTRUCTION}",
            f"Analyze the following contract text:\n\n{text}{_JSON_STRICT_INSTRUCTION}",
        ]

        for attempt, user_message in enumerate(prompts):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self.system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            raw = response.content[0].text.strip()

            # Strip markdown code fences the model may add despite instructions
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                raw = raw.strip()

            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                if attempt == len(prompts) - 1:
                    raise ValueError(
                        f"Failed to parse JSON after {len(prompts)} attempts. "
                        f"Last raw response:\n{raw}"
                    )

        raise ValueError("Unexpected exit from analyze_structured retry loop")
