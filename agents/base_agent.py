import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


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
