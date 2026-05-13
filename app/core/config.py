import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv(dotenv_path=".env")
load_dotenv(dotenv_path=".env.example")


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    groq_api_key: str | None
    ocr_provider: str
    openai_extraction_model: str
    openai_structuring_model: str
    groq_extraction_model: str
    groq_structuring_model: str
    api_host: str
    api_port: int
    request_timeout_seconds: int
    cors_origins: list[str]


def _clean_env_value(value: str | None) -> str | None:
    if not value:
        return None

    cleaned = value.strip()
    placeholder_prefixes = (
        "your-",
        "your_",
        "replace-",
        "replace_",
        "example-",
        "example_",
    )

    if cleaned.lower().startswith(placeholder_prefixes):
        return None

    return cleaned


def _default_cors_origins() -> list[str]:
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ]


def _listen_host() -> str:
    explicit = os.getenv("API_HOST")
    if explicit is not None and explicit.strip():
        return explicit.strip()
    return "0.0.0.0" if os.getenv("PORT") else "127.0.0.1"


def _listen_port() -> int:
    return int(os.getenv("PORT") or os.getenv("API_PORT") or "8001")


@lru_cache
def get_settings() -> Settings:
    cors_origins = os.getenv("CORS_ORIGINS")
    return Settings(
        openai_api_key=_clean_env_value(os.getenv("OPENAI_API_KEY")),
        groq_api_key=_clean_env_value(os.getenv("GROQ_API_KEY")),
        ocr_provider=os.getenv("OCR_PROVIDER", "groq").lower(),
        openai_extraction_model=os.getenv("OPENAI_EXTRACTION_MODEL", "gpt-4.1-mini"),
        openai_structuring_model=os.getenv("OPENAI_STRUCTURING_MODEL", "gpt-4.1-mini"),
        groq_extraction_model=os.getenv(
            "GROQ_EXTRACTION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"
        ),
        groq_structuring_model=os.getenv(
            "GROQ_STRUCTURING_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"
        ),
        api_host=_listen_host(),
        api_port=_listen_port(),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "180")),
        cors_origins=(
            [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
            if cors_origins
            else _default_cors_origins()
        ),
    )
