from __future__ import annotations

import os
import ssl
from dataclasses import dataclass, field

import certifi
from dotenv import load_dotenv

load_dotenv()

DEFAULT_EMBEDDING_MODEL = "gemini-embedding-2-preview"
DEFAULT_CHAT_MODEL = "gemini-3.1-flash-lite"
DEFAULT_CHAT_MODEL_PROVIDER = "google_genai"
# DEFAULT_CHAT_MODEL = "gpt-4o-mini"
# DEFAULT_CHAT_MODEL_PROVIDER = "openai"
# DEFAULT_CHAT_MODEL = "deepseek/deepseek-chat-v3.1"
# DEFAULT_CHAT_MODEL_PROVIDER = "openai"
DEFAULT_COLLECTION_NAME = "DocumentHelper"
DEFAULT_SCRAPING_URL = "https://docs.langchain.com"
DEFAULT_MAX_TOKENS_PER_MINUTE = 95000
DEFAULT_RATE_LIMIT_ENCODING = "cl100k_base"
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_TEXT_SPLITTER_ENCODING = "cl100k_base"
DEFAULT_EMBED_BATCH_SIZE = 64
DEFAULT_URL_CHUNK_SIZE = 30
DEFAULT_EMBED_SEMAPHORE_LIMIT = 1
DEFAULT_RETRIEVAL_K = 4
DEFAULT_TAVILY_MAX_DEPTH = 5
DEFAULT_TAVILY_MAX_BREADTH = 20
DEFAULT_TAVILY_LIMIT = 80
DEFAULT_CRAWL_MAX_DEPTH = 1
DEFAULT_CRAWL_EXTRACT_DEPTH = "advanced"
DEFAULT_EXTRACT_INSTRUCTIONS = (
    "Crawl only pages related to LangChain Third Party Tools or\n"
    "LangChain Integrations ."
)


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class QdrantSettings:
    url: str = field(default_factory=lambda: os.environ["QDRANT_URL"])
    api_key: str = field(default_factory=lambda: os.environ["QDRANT_API_KEY"])
    collection_name: str = field(
        default_factory=lambda: _env_str("QDRANT_COLLECTION_NAME", DEFAULT_COLLECTION_NAME)
    )
    prefer_grpc: bool = True


@dataclass(frozen=True)
class EmbeddingSettings:
    model: str = field(
        default_factory=lambda: _env_str("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    )


@dataclass(frozen=True)
class ChatModelSettings:
    model: str = field(
        default_factory=lambda: _env_str("CHAT_MODEL", DEFAULT_CHAT_MODEL)
    )
    provider: str = field(
        default_factory=lambda: _env_str("CHAT_MODEL_PROVIDER", DEFAULT_CHAT_MODEL_PROVIDER)
    )


@dataclass(frozen=True)
class RateLimiterSettings:
    max_tokens_per_minute: int = field(
        default_factory=lambda: _env_int(
            "MAX_TOKENS_PER_MINUTE", DEFAULT_MAX_TOKENS_PER_MINUTE
        )
    )
    encoding_name: str = field(
        default_factory=lambda: _env_str(
            "RATE_LIMIT_ENCODING", DEFAULT_RATE_LIMIT_ENCODING
        )
    )


@dataclass(frozen=True)
class ChunkingSettings:
    chunk_size: int = field(
        default_factory=lambda: _env_int("CHUNK_SIZE", DEFAULT_CHUNK_SIZE)
    )
    chunk_overlap: int = field(
        default_factory=lambda: _env_int("CHUNK_OVERLAP", DEFAULT_CHUNK_OVERLAP)
    )
    encoding_name: str = field(
        default_factory=lambda: _env_str(
            "TEXT_SPLITTER_ENCODING", DEFAULT_TEXT_SPLITTER_ENCODING
        )
    )
    url_chunk_size: int = field(
        default_factory=lambda: _env_int("URL_CHUNK_SIZE", DEFAULT_URL_CHUNK_SIZE)
    )


@dataclass(frozen=True)
class IngestionSettings:
    scraping_url: str = field(
        default_factory=lambda: _env_str("SCRAPING_URL", DEFAULT_SCRAPING_URL)
    )
    embed_batch_size: int = field(
        default_factory=lambda: _env_int("EMBED_BATCH_SIZE", DEFAULT_EMBED_BATCH_SIZE)
    )
    embed_semaphore_limit: int = field(
        default_factory=lambda: _env_int(
            "EMBED_SEMAPHORE_LIMIT", DEFAULT_EMBED_SEMAPHORE_LIMIT
        )
    )
    tavily_max_depth: int = field(
        default_factory=lambda: _env_int("TAVILY_MAX_DEPTH", DEFAULT_TAVILY_MAX_DEPTH)
    )
    tavily_max_breadth: int = field(
        default_factory=lambda: _env_int(
            "TAVILY_MAX_BREADTH", DEFAULT_TAVILY_MAX_BREADTH
        )
    )
    tavily_limit: int = field(
        default_factory=lambda: _env_int("TAVILY_LIMIT", DEFAULT_TAVILY_LIMIT)
    )
    crawl_max_depth: int = field(
        default_factory=lambda: _env_int("CRAWL_MAX_DEPTH", DEFAULT_CRAWL_MAX_DEPTH)
    )
    crawl_extract_depth: str = field(
        default_factory=lambda: _env_str(
            "CRAWL_EXTRACT_DEPTH", DEFAULT_CRAWL_EXTRACT_DEPTH
        )
    )
    extract_instructions: str = field(
        default_factory=lambda: _env_str(
            "EXTRACT_INSTRUCTIONS", DEFAULT_EXTRACT_INSTRUCTIONS
        )
    )


@dataclass(frozen=True)
class RetrievalSettings:
    k: int = field(default_factory=lambda: _env_int("RETRIEVAL_K", DEFAULT_RETRIEVAL_K))


def configure_ssl() -> None:
    ssl.create_default_context(cafile=certifi.where())
    os.environ["SSL_CERT_FILE"] = certifi.where()
    os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
