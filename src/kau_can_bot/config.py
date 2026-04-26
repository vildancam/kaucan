from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"
PAGES_PATH = DATA_DIR / "pages.jsonl"
INDEX_PATH = DATA_DIR / "search_index.joblib"
QUERY_LOG_PATH = LOG_DIR / "queries.jsonl"
INTERACTION_LOG_PATH = LOG_DIR / "interactions.jsonl"
FEEDBACK_LOG_PATH = LOG_DIR / "feedback.jsonl"
USER_MEMORY_PATH = DATA_DIR / "user_memory.json"

FALLBACK_RESPONSE = (
    "⚠️ Bu konuda güvenilir bir bilgiye ulaşamadım. En doğru bilgi için fakülte "
    "ile iletişime geçmenizi öneririm."
)

POLITE_LANGUAGE_RESPONSE = (
    "⚠️ Lütfen akademik ve uygun bir dil kullanınız. Size yardımcı olmaktan "
    "memnuniyet duyarım."
)

WELCOME_MESSAGE = (
    "👋 Merhaba, ben KAÜCAN Beta - Kafkas Üniversitesi Dijital Asistanı. İİBF hakkında "
    "duyurular, akademik bilgiler, personel, iletişim, sınavlar, yemek menüsü ve "
    "diğer konularda yardımcı olabilirim."
)


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    target_url: str = os.getenv("KAU_TARGET_URL", "https://kafkas.edu.tr/iibf")
    allowed_domain: str = os.getenv("KAU_ALLOWED_DOMAIN", "kafkas.edu.tr")
    crawl_scope: str = os.getenv("KAU_CRAWL_SCOPE", "faculty").strip().lower()
    max_pages: int = int(os.getenv("KAU_MAX_PAGES", "1000"))
    request_timeout: int = int(os.getenv("KAU_REQUEST_TIMEOUT", "20"))
    request_delay: float = float(os.getenv("KAU_REQUEST_DELAY", "0.3"))
    rate_limit_wait: float = float(os.getenv("KAU_RATE_LIMIT_WAIT", "65"))
    max_retries: int = int(os.getenv("KAU_MAX_RETRIES", "2"))
    chunk_size: int = int(os.getenv("KAU_CHUNK_SIZE", "1200"))
    chunk_overlap: int = int(os.getenv("KAU_CHUNK_OVERLAP", "180"))
    top_k: int = int(os.getenv("KAU_TOP_K", "5"))
    use_learning_expansion: bool = env_bool("KAU_USE_LEARNING_EXPANSION", True)
    llm_provider: str = os.getenv("KAU_LLM_PROVIDER", "ollama").strip().lower()
    use_openai: bool = env_bool("KAU_USE_OPENAI", True)
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5-chat-latest")
    openai_timeout: float = float(os.getenv("OPENAI_TIMEOUT", "30"))
    openai_max_output_tokens: int = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "900"))
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2")
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    ollama_timeout: float = float(os.getenv("OLLAMA_TIMEOUT", "120"))
    user_agent: str = os.getenv(
        "KAU_USER_AGENT",
        "KAU-CAN-ChatBot/0.1 (+https://kafkas.edu.tr/iibf)",
    )


def ensure_runtime_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
