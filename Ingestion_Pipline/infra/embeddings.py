from __future__ import annotations

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from Ingestion_Pipline.config.settings import DEFAULT_EMBEDDING_MODEL, EmbeddingSettings


def build_embeddings(
    settings: EmbeddingSettings | None = None,
) -> GoogleGenerativeAIEmbeddings:
    settings = settings or EmbeddingSettings()
    return GoogleGenerativeAIEmbeddings(model=settings.model or DEFAULT_EMBEDDING_MODEL)
