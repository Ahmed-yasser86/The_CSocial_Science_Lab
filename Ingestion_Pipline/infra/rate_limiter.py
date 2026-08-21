from __future__ import annotations

import asyncio
import time

import tiktoken
from langchain_core.documents import Document
from rich.console import Console

from Ingestion_Pipline.config.settings import DEFAULT_MAX_TOKENS_PER_MINUTE, DEFAULT_RATE_LIMIT_ENCODING

console = Console()

_WINDOW_SECONDS = 70


class TokenRateLimiter:
    def __init__(
        self,
        max_tokens_per_minute: int = DEFAULT_MAX_TOKENS_PER_MINUTE,
        encoding_name: str = DEFAULT_RATE_LIMIT_ENCODING,
    ):
        self.max_tokens_per_minute = max_tokens_per_minute
        self.encoding = tiktoken.get_encoding(encoding_name)

        self.tokens_used = 0
        self.window_start = time.monotonic()

        self._lock = asyncio.Lock()

    def count_tokens(self, docs: list[Document]) -> int:
        return sum(len(self.encoding.encode(doc.page_content)) for doc in docs)

    def _split_doc_into_sized_chunks(self, doc: Document) -> list[Document]:
        tokens = self.encoding.encode(doc.page_content)
        if len(tokens) <= self.max_tokens_per_minute:
            return [doc]

        chunks: list[Document] = []
        metadata = getattr(doc, "metadata", None)
        for i in range(0, len(tokens), self.max_tokens_per_minute):
            chunk_tokens = tokens[i : i + self.max_tokens_per_minute]
            chunks.append(
                Document(
                    page_content=self.encoding.decode(chunk_tokens),
                    metadata=metadata,
                )
            )

        return chunks

    def _partition_docs_by_limit(self, docs: list[Document]) -> list[list[Document]]:
        batches: list[list[Document]] = []
        current_batch: list[Document] = []
        current_tokens = 0

        for doc in docs:
            doc_tokens = len(self.encoding.encode(doc.page_content))
            if doc_tokens > self.max_tokens_per_minute:
                # Split oversized documents into token-sized chunks.
                for subdoc in self._split_doc_into_sized_chunks(doc):
                    subdoc_tokens = len(self.encoding.encode(subdoc.page_content))
                    if current_batch and current_tokens + subdoc_tokens > self.max_tokens_per_minute:
                        batches.append(current_batch)
                        current_batch = []
                        current_tokens = 0
                    current_batch.append(subdoc)
                    current_tokens += subdoc_tokens
            else:
                if current_batch and current_tokens + doc_tokens > self.max_tokens_per_minute:
                    batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0
                current_batch.append(doc)
                current_tokens += doc_tokens

        if current_batch:
            batches.append(current_batch)

        return batches

    async def acquire(self, docs: list[Document]):
        batches = self._partition_docs_by_limit(docs)
        if len(batches) > 1:
            console.print(
                f"[yellow]Split request into {len(batches)} sub-batches to respect TPM limit {self.max_tokens_per_minute}.[/yellow]"
            )

        async with self._lock:
            for batch in batches:
                batch_tokens = self.count_tokens(batch)

                while True:
                    now = time.monotonic()
                    elapsed = now - self.window_start

                    if elapsed >= _WINDOW_SECONDS:
                        self.tokens_used = 0
                        self.window_start = now

                    if self.tokens_used + batch_tokens <= self.max_tokens_per_minute:
                        self.tokens_used += batch_tokens
                        console.print(
                            f"[green]TPM: {self.tokens_used}/{self.max_tokens_per_minute}[/green]"
                        )
                        break

                    wait_time = _WINDOW_SECONDS - elapsed
                    if wait_time <= 0:
                        wait_time = _WINDOW_SECONDS

                    console.print(
                        f"[yellow]TPM limit reached. Waiting {wait_time:.1f}s...[/yellow]"
                    )
                    await asyncio.sleep(wait_time)
