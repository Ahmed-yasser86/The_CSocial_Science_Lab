from __future__ import annotations

import asyncio

from langchain_core.documents import Document
from langchain_tavily import TavilyExtract, TavilyMap
from rich.console import Console

from Ingestion_Pipline.config.settings import DEFAULT_URL_CHUNK_SIZE, IngestionSettings
from ingestion.chunking import build_documents, chunk_urls
from ingestion.tavily_client import extract_urls, get_site_urls

console = Console()


async def extract_all_batches(
    tavily_extract: TavilyExtract,
    url_batches: list[list[str]],
    settings: IngestionSettings | None = None,
):
    total_urls = sum(len(batch) for batch in url_batches)
    console.print(
        f"[bold yellow]📦 Processing {total_urls} URLs in {len(url_batches)} batches[/bold yellow]"
    )

    tasks = [
        extract_urls(tavily_extract, batch, i + 1, settings)
        for i, batch in enumerate(url_batches)
    ]

    return await asyncio.gather(*tasks, return_exceptions=True)


async def retrieve_all_docs(
    tavily_map: TavilyMap,
    tavily_extract: TavilyExtract,
    settings: IngestionSettings | None = None,
    url_chunk_size: int = DEFAULT_URL_CHUNK_SIZE,
) -> list[Document]:
    settings = settings or IngestionSettings()

    urls = get_site_urls(tavily_map, settings)
    url_batches = chunk_urls(urls, chunk_size=url_chunk_size)
    results = await extract_all_batches(tavily_extract, url_batches, settings)

    return build_documents(results)
