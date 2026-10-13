"""Central place for app settings.

Settings come from environment variables, which we load from the .env file.
The rest of the code asks this module for settings instead of reading
os.environ directly, so there is one place to look when something is misconfigured.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

PLACEHOLDER_KEY = "paste-your-key-here"


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    gemini_api_key: str
    gemini_model: str
    gemini_fallback_models: list[str]

    @property
    def has_gemini_key(self) -> bool:
        return bool(self.gemini_api_key) and self.gemini_api_key != PLACEHOLDER_KEY


def get_settings() -> Settings:
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "gemini"),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        gemini_fallback_models=[
            name.strip() for name in os.getenv("GEMINI_FALLBACK_MODELS", "").split(",") if name.strip()
        ],
    )
