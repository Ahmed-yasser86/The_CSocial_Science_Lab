from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rich.console import Console

from Ingestion_Pipline.config.settings import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_TEXT_SPLITTER_ENCODING,
    DEFAULT_URL_CHUNK_SIZE,
)

console = Console()


def split_text(
    document: list[Document],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    encoding_name: str = DEFAULT_TEXT_SPLITTER_ENCODING,
) -> list[Document]:
    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=encoding_name,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return text_splitter.split_documents(document)


def chunk_urls(
    urls: list[str],
    chunk_size: int = DEFAULT_URL_CHUNK_SIZE,
) -> list[list[str]]:
    "SPLIT URLS INTO CHUNKS"
    return [urls[i : i + chunk_size] for i in range(0, len(urls), chunk_size)]


def build_documents(results) -> list[Document]:
    all_docs = []
    failed_batches = 0

    for result in results:
        if isinstance(result, Exception):
            console.print(f"[red]❌ Batch failed: {result}[/red]")
            failed_batches += 1
            continue

        for page in result:
            all_docs.append(
                Document(
                    page_content=page["raw_content"],
                    metadata={"source": page["url"]},
                )
            )

    console.print(
        f"[bold green]🎉 Done! Created {len(all_docs)} documents "
        f"({failed_batches} failed batches).[/bold green]"
    )

    return all_docs
