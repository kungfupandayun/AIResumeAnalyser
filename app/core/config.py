from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OPENAI_API_KEY: Optional[str] = None
    EMBED_MODEL: str = "text-embedding-3-small"
    CHAT_MODEL: str = "gpt-4o-mini"
    SYNONYMS_PATH: Path = Path(__file__).parent.parent / "data" / "synonyms.yaml"

    WEIGHT_SKILLS: float = 0.35
    WEIGHT_EXPERIENCE: float = 0.30
    WEIGHT_SENIORITY: float = 0.15
    WEIGHT_SUMMARY: float = 0.10
    WEIGHT_EDUCATION: float = 0.10

    AI_EMBED_TIMEOUT_S: float = 20.0
    AI_CHAT_TIMEOUT_S: float = 30.0
    AI_CIRCUIT_THRESHOLD: int = 3
    AI_CIRCUIT_WINDOW_S: float = 60.0

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
