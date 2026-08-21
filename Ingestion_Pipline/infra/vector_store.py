from __future__ import annotations

import asyncio

from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, VectorParams
from langchain_qdrant import QdrantVectorStore

from Ingestion_Pipline.config.settings import DEFAULT_COLLECTION_NAME, QdrantSettings
from Ingestion_Pipline.infra.retry_policies import document_add_retry, vector_dimension_retry
from Ingestion_Pipline.utils.logger import log_error, log_info, log_success


@vector_dimension_retry()
def get_vector_size(embedding) -> int:
    vector = embedding.embed_query("dimension check")
    return len(vector)


async def get_vector_db(
    embedding,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    settings: QdrantSettings | None = None,
) -> QdrantVectorStore:
    settings = settings or QdrantSettings()
    return  QdrantVectorStore.from_existing_collection(
        embedding=embedding,
        collection_name=collection_name or settings.collection_name,
        url=settings.url,
        api_key=settings.api_key,
    )


async def  create_empty_collection(
    embedding,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    distance: Distance = Distance.COSINE,
    settings: QdrantSettings | None = None,
) -> QdrantVectorStore:
    settings = settings or QdrantSettings()
    resolved_collection_name = collection_name or settings.collection_name

    try:
        client = QdrantClient(url=settings.url, api_key=settings.api_key)

        vector_size =  get_vector_size(embedding)

        if not client.collection_exists(resolved_collection_name):
            client.create_collection(
                collection_name=resolved_collection_name,
                vectors_config=VectorParams(size=vector_size, distance=distance),
            )
            log_success(f"Collection '{resolved_collection_name}' created successfully.")
        else:
            log_info(f"Collection '{resolved_collection_name}' already exists.")

        return await get_vector_db(
            embedding=embedding,
            collection_name=resolved_collection_name,
            settings=settings,
        )

    except UnexpectedResponse as e:
        log_error(f"Qdrant returned an unexpected response: {e}")
        raise

    except Exception as e:
        log_error(f"Failed to create or connect to collection: {e}")
        raise


async def create_vector_db_with_docs(
    docs: list[Document],
    embeddings,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    settings: QdrantSettings | None = None,
) -> QdrantVectorStore:
    settings = settings or QdrantSettings()
    return QdrantVectorStore.from_documents(
        docs,
        embeddings,
        url=settings.url,
        prefer_grpc=settings.prefer_grpc,
        api_key=settings.api_key,
        collection_name=collection_name or settings.collection_name,
    )


@document_add_retry()
async def add_documents_with_retry(
    vector_store: QdrantVectorStore,
    docs: list[Document],
) -> None:
    await asyncio.to_thread(vector_store.add_documents, docs)
