from __future__ import annotations

import asyncio
import logging

from qdrant_client.models import Distance
from rich.console import Console
from rich.panel import Panel

from Ingestion_Pipline.config.settings import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_EMBED_BATCH_SIZE,
    DEFAULT_EMBED_SEMAPHORE_LIMIT,
    DEFAULT_SCRAPING_URL,
    EmbeddingSettings,
    IngestionSettings,
    RateLimiterSettings,
    configure_ssl,
)
from Ingestion_Pipline.infra.embeddings import build_embeddings
from Ingestion_Pipline.infra.rate_limiter import TokenRateLimiter
from Ingestion_Pipline.infra.vector_store import (
    add_documents_with_retry,
    create_empty_collection,
    create_vector_db_with_docs,
    get_vector_db,
    get_vector_size as _get_vector_size,
)
from ingestion.chunking import build_documents, split_text
from ingestion.chunking import chunk_urls as _chunk_urls
from ingestion.embedding_pipeline import embed_documents_in_batches, ResilientEmbeddingPipeline
from ingestion.extraction_pipeline import extract_all_batches, retrieve_all_docs
from ingestion.tavily_client import (
    build_tavily_crawl,
    build_tavily_extract,
    build_tavily_map,
    docs_crawling,
    doc_scrolling_using_tavily_langchain,
    extract_urls,
    get_site_urls,
)
from utils.logger import log_header

logging.basicConfig(level=logging.INFO)
console = Console()

configure_ssl()

_ingestion_settings = IngestionSettings()
_rate_limiter_settings = RateLimiterSettings()

embeddings = build_embeddings(EmbeddingSettings())

ScrapingUrl = _ingestion_settings.scraping_url or DEFAULT_SCRAPING_URL
tavily_extract = build_tavily_extract()
tavily_map = build_tavily_map(_ingestion_settings)
tavily_crewl = build_tavily_crawl()
Collection_Name = DEFAULT_COLLECTION_NAME

semaphore = asyncio.Semaphore(
    _ingestion_settings.embed_semaphore_limit or DEFAULT_EMBED_SEMAPHORE_LIMIT
)

limiter = TokenRateLimiter(
    max_tokens_per_minute=_rate_limiter_settings.max_tokens_per_minute,
    encoding_name=_rate_limiter_settings.encoding_name,
)


async def ProcessBatch(
    vector_store,
    batch,
    batch_num: int,
):
    pipeline = ResilientEmbeddingPipeline(
        batch_size=_ingestion_settings.embed_batch_size,
        semaphore_limit=_ingestion_settings.embed_semaphore_limit,
        token_rate_limiter=limiter,
    )
    await pipeline.start_worker()
    return await pipeline.embed_documents(vector_store, batch, request_id=f"batch_{batch_num}")


def get_vector_size(embedding) -> int:
    return _get_vector_size(embedding)


async def createEmptyCollection(
    embedding,
    collection_name: str,
    distance: Distance = Distance.COSINE,
):
    return await create_empty_collection(embedding, collection_name, distance)


def SplitText(document, chunk_size, chunk_overlap):
    return split_text(document, chunk_size, chunk_overlap)


async def createVectoreDBWithDocs(docs, embeddings):
    return await create_vector_db_with_docs(docs, embeddings, Collection_Name)


async def GettingVectoreDB(embedding, collection_name: str = Collection_Name):
    return await get_vector_db(embedding, collection_name)


async def AddDocumentsWithRetry(vector_store, docs) -> None:
    await add_documents_with_retry(vector_store, docs)


def DocsCruling():

    log_header("document ingestion pipline started")
    return docs_crawling(tavily_crewl, _ingestion_settings)


def docScrollingUsingTavilyLangChain():
    return doc_scrolling_using_tavily_langchain(
        tavily_map, tavily_extract, _ingestion_settings
    )


async def EmbedDocumentsInBatches(
    vector_store,
    docs,
    batch_size: int = DEFAULT_EMBED_BATCH_SIZE,
):
    return await embed_documents_in_batches(
        vector_store, docs, batch_size, semaphore, limiter
    )


def Chunk_urls(urls: list[str], chunk_size: int = 3) -> list[list[str]]:
    "SPLIT URLS INTO CHUNKS"
    return _chunk_urls(urls, chunk_size)


async def Extract_Urls(urls: list[str], batch_num: int):
    """Extract docs from a batch of URLs."""
    return await extract_urls(tavily_extract, urls, batch_num, _ingestion_settings)


def GetSiteUrls() -> list[str]:
    return get_site_urls(tavily_map, _ingestion_settings)


async def ExtractAllBatches(url_batches: list[list[str]]):
    return await extract_all_batches(tavily_extract, url_batches, _ingestion_settings)


def BuildDocuments(results):
    return build_documents(results)


async def RetriveAllDocs():
    return await retrieve_all_docs(tavily_map, tavily_extract, _ingestion_settings)


async def EmbedDocumentsToVectoreDb(urls:list[list[str]],Collection_Name):
      ## this extract docs from supplied urls
       result = await ExtractAllBatches(urls)
       docs = BuildDocuments(result)
       texts = SplitText(docs, DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP)
       vdb = await createEmptyCollection(embeddings, Collection_Name)
       Batchingresult = await EmbedDocumentsInBatches(vdb, texts)
       return Batchingresult

