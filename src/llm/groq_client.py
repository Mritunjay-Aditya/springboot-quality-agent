import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

load_dotenv(Path(__file__).parents[2] / ".env")


class GroqClient:
    def __init__(self, model: str = "openai/gpt-oss-120b") -> None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is required for LLM test generation")
        self.client = Groq(api_key=api_key)
        self.model = model

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Groq returned an empty response")
        return content
