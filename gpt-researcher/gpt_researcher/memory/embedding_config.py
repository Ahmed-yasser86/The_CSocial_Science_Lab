"""Configuration for resilient embedding pipeline.

Provides sensible defaults and configuration templates for different use cases.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class EmbeddingConfig:
    """Configuration for ResilientEmbeddingPipeline."""
    
    # Provider and model
    provider: str = "openai"
    model: str = "text-embedding-3-small"
    
    # Rate limiting
    max_tokens_per_minute: int = 95000
    encoding_name: str = "cl100k_base"
    
    # Batch processing
    # Note: GPT Researcher doesn't batch embeddings, but pipeline auto-splits for safety
    # chunk_size=512 is a reasonable default to handle large batches safely
    chunk_size: int = 512  # Max documents per request (auto-batching)
    max_retries: int = 3   # Retry attempts
    
    # Logging
    log_dir: Optional[str] = None
    
    # Timeouts
    request_timeout: float = 600.0  # 10 minutes
    
    # Provider-specific kwargs
    additional_kwargs: dict = None
    
    def to_dict(self) -> dict:
        """Convert config to dictionary for pipeline initialization."""
        return {
            "embedding_provider": self.provider,
            "model": self.model,
            "max_tokens_per_minute": self.max_tokens_per_minute,
            "encoding_name": self.encoding_name,
            "chunk_size": self.chunk_size,
            "max_retries": self.max_retries,
            **(self.additional_kwargs or {}),
        }


# Preset configurations for different use cases

class ResearchPipelineConfig(EmbeddingConfig):
    """Configuration optimized for research pipelines (no data loss)."""
    
    def __init__(self):
        super().__init__(
            provider="openai",
            model="text-embedding-3-small",
            max_tokens_per_minute=95000,
            chunk_size=256,        # Smaller batches for safety
            max_retries=5,         # Higher retries for critical data
            request_timeout=900.0, # 15 minutes
        )


class HighThroughputConfig(EmbeddingConfig):
    """Configuration optimized for high throughput."""
    
    def __init__(self):
        super().__init__(
            provider="openai",
            model="text-embedding-3-small",
            max_tokens_per_minute=95000,
            chunk_size=1024,       # Larger batches for speed
            max_retries=2,         # Fewer retries
            request_timeout=300.0, # 5 minutes
        )


class LowCostConfig(EmbeddingConfig):
    """Configuration optimized for cost (uses smaller model)."""
    
    def __init__(self):
        super().__init__(
            provider="openai",
            model="text-embedding-3-small",
            max_tokens_per_minute=30000,  # Conservative rate limit
            chunk_size=256,
            max_retries=3,
            request_timeout=600.0,
        )


class LocalConfig(EmbeddingConfig):
    """Configuration for local/Ollama embeddings."""
    
    def __init__(self):
        super().__init__(
            provider="ollama",
            model="nomic-embed-text",
            max_tokens_per_minute=999999,  # No rate limit for local
            chunk_size=512,
            max_retries=2,
            request_timeout=300.0,
        )


class MultiProviderConfig:
    """Configuration for multi-provider setup with fallback."""
    
    def __init__(self):
        self.primary = ResearchPipelineConfig()
        self.fallback = LocalConfig()


# Helper to get config by name
def get_config(name: str) -> EmbeddingConfig:
    """Get preset configuration by name.
    
    Args:
        name: Config name (research, throughput, low_cost, local)
        
    Returns:
        EmbeddingConfig instance
        
    Raises:
        ValueError: If config name not found
    """
    configs = {
        "research": ResearchPipelineConfig,
        "throughput": HighThroughputConfig,
        "low_cost": LowCostConfig,
        "local": LocalConfig,
    }
    
    if name not in configs:
        raise ValueError(f"Unknown config: {name}. Available: {list(configs.keys())}")
    
    return configs[name]()


# Example environment-based config loader
def load_from_env() -> EmbeddingConfig:
    """Load config from environment variables.
    
    Environment variables:
    - EMBEDDING_PROVIDER: Provider name (default: openai)
    - EMBEDDING_MODEL: Model name
    - EMBEDDING_TPM: Max tokens per minute
    - EMBEDDING_CHUNK_SIZE: Chunk size
    - EMBEDDING_MAX_RETRIES: Max retries
    - EMBEDDING_LOG_DIR: Log directory
    - EMBEDDING_TIMEOUT: Request timeout
    """
    import os
    
    config = EmbeddingConfig(
        provider=os.getenv("EMBEDDING_PROVIDER", "openai"),
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        max_tokens_per_minute=int(os.getenv("EMBEDDING_TPM", "95000")),
        chunk_size=int(os.getenv("EMBEDDING_CHUNK_SIZE", "512")),
        max_retries=int(os.getenv("EMBEDDING_MAX_RETRIES", "3")),
        log_dir=os.getenv("EMBEDDING_LOG_DIR", None),
        request_timeout=float(os.getenv("EMBEDDING_TIMEOUT", "600")),
    )
    
    return config
