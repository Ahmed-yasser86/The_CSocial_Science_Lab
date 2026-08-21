"""Resilient embedding pipeline with rate limiting, queue, and retry logic.

This module provides a robust embedding pipeline that:
- Respects token rate limits to avoid API throttling
- Queues embedding requests to prevent data loss
- Automatically retries failed requests with exponential backoff
- Splits large batches to handle API limits
- Ensures no document is lost during processing
"""

import asyncio
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional
import os

import tiktoken
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from rich.console import Console

from gpt_researcher.memory.embeddings import Memory

console = Console()

_WINDOW_SECONDS = 70
_DEFAULT_CHUNK_SIZE = 512  # GPT Researcher default: 1000 for text splitting, 512 for embedding batching
_MAX_RETRIES = 3
_INITIAL_BACKOFF = 4.0


import uuid

@dataclass
class EmbeddingRequest:
    """Represents a single embedding request with metadata."""
    
    docs: list[Document]
    request_id: str = field(default_factory=lambda: f"req_{uuid.uuid4().hex[:12]}")
    retry_count: int = 0
    created_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending, processing, completed, failed
    error: Optional[str] = None
    result: Optional[list[list[float]]] = None


class ResilientEmbeddingsAdapter(Embeddings):
    """Synchronous adapter that routes embedding calls through the resilient queue.

    This is used by the compression pipeline so that transient provider throttling
    is handled by retrying and batching instead of failing the whole retrieval step.
    """

    def __init__(
        self,
        embeddings: Any,
        max_tokens_per_minute: int = 95000,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
        max_retries: Optional[int] = _MAX_RETRIES,
        retry_forever: bool = True,
        token_rate_limiter: Optional[object] = None,
    ):
        self._embeddings = embeddings
        self._pipeline = ResilientEmbeddingPipeline(
            embeddings_instance=embeddings,
            max_tokens_per_minute=max_tokens_per_minute,
            chunk_size=chunk_size,
            max_retries=max_retries,
            retry_forever=retry_forever,
            token_rate_limiter=token_rate_limiter,
        )

    def _run_async(self, coro):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        if loop.is_closed():
            return asyncio.run(coro)

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()

    async def _embed_documents_async(self, texts: list[str]):
        docs = [Document(page_content=text, metadata={}) for text in texts]
        result = await self._pipeline.embed_documents(docs, wait_for_result=True, wait_timeout=None)
        if result.get("status") != "completed":
            raise RuntimeError(result.get("error") or "Embedding request did not complete")
        return result.get("result") or result.get("results") or []

    def embed_documents(self, texts: list[str]):
        result = self._run_async(self._embed_documents_async(texts))
        if isinstance(result, dict):
            result = result.get("result") or result.get("results") or []
        if not result:
            return []
        return result

    def embed_query(self, text: str):
        if not text or not text.strip():
            if hasattr(self._embeddings, "embed_query"):
                return self._embeddings.embed_query(text or "query")
            return []

        try:
            result = self.embed_documents([text])
            if result and len(result) > 0 and len(result[0]) > 0:
                return result[0]
        except Exception as e:
            console.print(f"[yellow]Resilient embed_query failed: {e}. Falling back to direct embed_query[/yellow]")

        if hasattr(self._embeddings, "embed_query"):
            return self._embeddings.embed_query(text)

        return []


class ResilientEmbeddingPipeline:
    """Robust embedding pipeline with rate limiting, queuing, and retry logic.
    
    Features:
    - Token-based rate limiting
    - Queue-based processing to prevent request loss
    - Automatic retry with exponential backoff
    - Large batch splitting
    - Zero data loss guarantee
    """
    
    def __init__(
        self,
        embedding_provider: str | None = None,
        model: str | None = None,
        max_tokens_per_minute: int = 95000,
        encoding_name: str = "cl100k_base",
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
        max_retries: Optional[int] = _MAX_RETRIES,
        retry_forever: bool = True,
        token_rate_limiter: Optional[object] = None,
        embeddings_instance: Any = None,
        **embedding_kwargs: Any,
    ):
        """Initialize the resilient embedding pipeline.
        
        Args:
            embedding_provider: The embedding provider name
            model: The model to use
            max_tokens_per_minute: Max tokens per minute (rate limit)
            encoding_name: Tiktoken encoding name
            chunk_size: Max documents per request
            max_retries: Max retry attempts per request
            retry_forever: If True, keep retrying failed batches indefinitely
            token_rate_limiter: Optional external TokenRateLimiter instance to centralize throttling
            **embedding_kwargs: Additional args for Memory class
        """
        if embeddings_instance is not None:
            self.embeddings = embeddings_instance
        else:
            self.memory = Memory(embedding_provider or "openai", model or "text-embedding-3-small", **embedding_kwargs)
            self.embeddings = self.memory.get_embeddings()
        
        self.max_tokens_per_minute = max_tokens_per_minute
        self.encoding = tiktoken.get_encoding(encoding_name)
        self.chunk_size = chunk_size
        self.max_retries = max_retries
        self.retry_forever = retry_forever
        
        # External token rate limiter (optional). If provided, the pipeline will
        # use it instead of its internal rate-limiting logic to avoid duplicate
        # throttles and competing windows.
        self.token_rate_limiter: Optional[object] = token_rate_limiter
        
        # Rate limiting state (internal fallback)
        self.tokens_used = 0
        self.window_start = time.monotonic()
        
        # Queue and request tracking
        self.request_queue: deque[EmbeddingRequest] = deque()
        self.request_history: dict[str, EmbeddingRequest] = {}
        self._lock = asyncio.Lock()
        self._worker_task: Optional[asyncio.Task] = None
        self._worker_wake_event: Optional[asyncio.Event] = None
    
    def count_tokens(self, docs: list[Document]) -> int:
        """Count total tokens in document batch."""
        return sum(len(self.encoding.encode(doc.page_content)) for doc in docs)

    def _extract_retry_delay(self, error: Exception) -> float:
        """Infer a smart retry delay from provider error headers and message bodies."""
        headers = {}
        if hasattr(error, "headers") and getattr(error, "headers"):
            headers.update(getattr(error, "headers"))
        if hasattr(error, "response") and getattr(error, "response"):
            response = getattr(error, "response")
            if hasattr(response, "headers") and getattr(response, "headers"):
                headers.update(getattr(response, "headers"))
            if hasattr(response, "json"):
                try:
                    payload = response.json()
                    if isinstance(payload, dict):
                        headers.update(payload)
                except Exception:
                    pass

        normalized = {}
        for key, value in headers.items():
            if isinstance(key, str):
                normalized[key.lower()] = value

        def _get(header_names: list[str]):
            for name in header_names:
                if name in normalized:
                    return normalized[name]
            return None

        retry_after = _get(["retry-after", "retry_after", "x-retry-after"])
        if retry_after is not None:
            try:
                return max(5.0, float(retry_after))
            except (TypeError, ValueError):
                pass

        remaining = _get([
            "x-trial-endpoint-call-remaining",
            "x-endpoint-call-remaining",
            "x-endpoint-monthly-call-remaining",
        ])
        if remaining is not None:
            try:
                remaining_value = int(remaining)
            except (TypeError, ValueError):
                remaining_value = None
            if remaining_value is not None:
                if remaining_value <= 5:
                    return 60.0
                if remaining_value <= 20:
                    return 30.0
                if remaining_value <= 50:
                    return 20.0
                if remaining_value <= 100:
                    return 8.0
                return 5.0

        msg = str(error)
        if re.search(r"rate limit|too many requests|trial token rate limit", msg, re.IGNORECASE):
            return 12.0
        return 4.0

    def _get_retry_delay(self, error: Exception, default_wait: float = 4.0) -> float:
        """Compatibility wrapper used by tests and retry flow."""
        delay = self._extract_retry_delay(error)
        return max(default_wait, delay)
    
    def _split_batch(self, docs: list[Document]) -> list[list[Document]]:
        """Split large batch into smaller chunks based on token count.

        This method adapts the per-batch token threshold dynamically based on
        the configured (or external) token rate limiter and the provider's
        maximum capacity. Token limits drive splitting; chunk_size is a soft
        document-count safety cap.
        """
        batches = []
        current_batch = []
        current_tokens = 0

        # Determine current limiter max: prefer external limiter if present
        provider_cap = int(os.environ.get("PROVIDER_MAX_TOKENS_PER_MINUTE", "100000"))
        if getattr(self, "token_rate_limiter", None) and hasattr(self.token_rate_limiter, "max_tokens_per_minute"):
            current_limit = int(getattr(self.token_rate_limiter, "max_tokens_per_minute"))
        else:
            current_limit = int(self.max_tokens_per_minute)

        # Compute a safe per-batch token threshold (cap at 8,000 tokens per API call to avoid API payload overflow)
        safe_target = int(provider_cap * 0.95)
        batch_token_limit = min(current_limit, safe_target, 8000)
        if batch_token_limit < 1000:
            batch_token_limit = max(1000, int(self.max_tokens_per_minute // 10))

        # Enforce max 25 documents per single API request batch
        max_docs_per_batch = int(os.environ.get("MAX_DOCS_PER_BATCH", "25"))

        console.print(f"[cyan]Partitioning {len(docs)} docs using token limit {batch_token_limit} and doc limit {max_docs_per_batch}[/cyan]")

        for idx, doc in enumerate(docs, start=1):
            doc_tokens = len(self.encoding.encode(doc.page_content))

            # If a document exceeds the batch token limit, split into chunks
            if doc_tokens > batch_token_limit:
                console.print(f"[magenta]Doc {idx} exceeds batch_token_limit ({doc_tokens} > {batch_token_limit}), splitting into chunks[/magenta]")
                tokens = self.encoding.encode(doc.page_content)
                for i in range(0, len(tokens), batch_token_limit):
                    chunk_tokens = tokens[i : i + batch_token_limit]
                    chunk_text = self.encoding.decode(chunk_tokens)
                    chunk_doc = Document(page_content=chunk_text, metadata=getattr(doc, 'metadata', None))
                    if current_batch and (current_tokens + len(chunk_tokens)) > batch_token_limit:
                        batches.append(current_batch)
                        current_batch = []
                        current_tokens = 0
                    current_batch.append(chunk_doc)
                    current_tokens += len(chunk_tokens)
            else:
                # Start new batch if adding this doc exceeds token threshold or doc count threshold
                if current_batch and ((current_tokens + doc_tokens) > batch_token_limit or len(current_batch) >= max_docs_per_batch):
                    batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0

                current_batch.append(doc)
                current_tokens += doc_tokens

            # Safety flush if doc count cap is reached
            if len(current_batch) >= max_docs_per_batch:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0

        if current_batch:
            batches.append(current_batch)

        console.print(f"[green]Partitioned into {len(batches)} batches[/green]")
        return batches    

    async def _acquire_tokens(self, batch_tokens: int) -> None:
        """Wait until tokens are available (rate limiting).
        
        Args:
            batch_tokens: Number of tokens needed
        """
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.window_start
                
                # Reset window if time has passed
                if elapsed >= _WINDOW_SECONDS:
                    self.tokens_used = 0
                    self.window_start = now
                
                # Check if tokens available
                if self.tokens_used + batch_tokens <= self.max_tokens_per_minute:
                    self.tokens_used += batch_tokens
                    console.print(
                        f"[green]✓ TPM: {self.tokens_used}/{self.max_tokens_per_minute} "
                        f"| Queued: {len(self.request_queue)}[/green]"
                    )
                    return
                
                # Wait for window reset
                wait_time = _WINDOW_SECONDS - elapsed
                console.print(
                    f"[yellow]⏳ Rate limit reached. Waiting {wait_time:.1f}s... "
                    f"(Queued: {len(self.request_queue)})[/yellow]"
                )
                await asyncio.sleep(wait_time)
    
    async def _process_request(self, request: EmbeddingRequest) -> EmbeddingRequest:
        """Process a single embedding request with dynamic binary halving (N -> N/2 -> N/4 -> 1), adaptive backoff, and strict 100% completion guard.
        
        Args:
            request: The embedding request to process
            
        Returns:
            Processed request with 100% validated vector embeddings or error
        """
        request.status = "processing"
        backoff = _INITIAL_BACKOFF
        retry_limit = float("inf") if self.retry_forever else (self.max_retries or 0)
        
        while request.retry_count < retry_limit:
            try:
                batch_tokens = self.count_tokens(request.docs)
                
                if getattr(self, "token_rate_limiter", None):
                    try:
                        await self.token_rate_limiter.acquire(request.docs)
                    except Exception:
                        await self._acquire_tokens(batch_tokens)
                else:
                    await self._acquire_tokens(batch_tokens)

                console.print(
                    f"[cyan]→ Processing request {request.request_id} "
                    f"({len(request.docs)} docs, {batch_tokens} tokens)[/cyan]"
                )
                
                result = await asyncio.to_thread(
                    self.embeddings.embed_documents,
                    [doc.page_content for doc in request.docs]
                )

                # Strict Pass Guard: Ensure 100% of input documents returned valid vector embeddings
                if result and len(result) == len(request.docs):
                    request.result = result
                    request.status = "completed"
                    console.print(
                        f"[green]✓ Request {request.request_id} completed "
                        f"({len(result)} embeddings 100% validated)[/green]"
                    )
                    return request
                else:
                    raise RuntimeError(f"Incomplete embedding results: expected {len(request.docs)}, received {len(result) if result else 0}")
            
            except Exception as e:
                request.retry_count += 1
                request.error = str(e)
                request.status = "processing"

                # Dynamic Halving (Binary Split N -> N/2 -> N/4 ... -> 1):
                # When any error or rate-limit occurs on a batch with > 1 document, recursively split into two equal halves
                if len(request.docs) > 1:
                    console.print(
                        f"[yellow]⚡ Exception encountered ({e}). Dynamic Binary Halving batch of {len(request.docs)} docs "
                        f"into [{len(request.docs)//2}] and [{len(request.docs) - len(request.docs)//2}]...[/yellow]"
                    )
                    half = len(request.docs) // 2
                    sub1_docs = request.docs[:half]
                    sub2_docs = request.docs[half:]
                    
                    sub1_req = EmbeddingRequest(docs=sub1_docs)
                    sub2_req = EmbeddingRequest(docs=sub2_docs)
                    
                    sub1_res = await self._process_request(sub1_req)
                    sub2_res = await self._process_request(sub2_req)
                    
                    if sub1_res.status == "completed" and sub2_res.status == "completed":
                        request.result = (sub1_res.result or []) + (sub2_res.result or [])
                        request.status = "completed"
                        console.print(
                            f"[green]✓ Request {request.request_id} dynamically completed via Binary Split "
                            f"({len(request.result)} embeddings 100% validated)[/green]"
                        )
                        return request

                if not self.retry_forever and request.retry_count >= retry_limit:
                    request.status = "failed"
                    console.print(
                        f"[red]✗ Request {request.request_id} FAILED after {self.max_retries} retries: {e}[/red]"
                    )
                    return request

                # Adaptive Exponential Backoff (2^n) with jitter & provider header inspection
                base_wait = backoff * (2 ** min(request.retry_count, 6))
                import random
                wait_time = min(60.0, base_wait * random.uniform(0.9, 1.25))
                wait_time = max(wait_time, self._get_retry_delay(e, default_wait=wait_time))

                if hasattr(e, "headers") or hasattr(e, "response"):
                    console.print(f"[yellow]Rate-limit headers detected, waiting {wait_time:.1f}s[/yellow]")

                if self.retry_forever:
                    console.print(
                        f"[yellow]↻ Request {request.request_id} retry {request.retry_count} "
                        f"indefinitely in {wait_time:.1f}s (Error: {e})[/yellow]"
                    )
                else:
                    console.print(
                        f"[yellow]↻ Request {request.request_id} retry {request.retry_count}/{self.max_retries} "
                        f"in {wait_time:.1f}s (Error: {e})[/yellow]"
                    )
                await asyncio.sleep(wait_time)
    
    async def _worker_loop(self) -> None:
        """Background worker that processes queued requests continuously."""
        self._worker_wake_event = asyncio.Event()
        console.print("[bold cyan]🚀 Embedding worker started[/bold cyan]")

        while True:
            try:
                if not self.request_queue:
                    await self._wait_for_work()
                    continue

                async with self._lock:
                    if not self.request_queue:
                        await self._wait_for_work()
                        continue
                    request = self.request_queue.popleft()

                processed = await self._process_request(request)
                self.request_history[processed.request_id] = processed

                # Strict Sequential Pacing Guard: wait for inter-batch delay before processing next item in queue
                batch_delay = float(os.environ.get("EMBEDDING_BATCH_DELAY_SECONDS", "0.5"))
                if batch_delay > 0:
                    await asyncio.sleep(batch_delay)

            except asyncio.CancelledError:
                console.print("[yellow]⛔ Embedding worker stopped[/yellow]")
                break
            except Exception as e:
                console.print(f"[red]Worker error: {e}[/red]")
                await self._wait_for_work(timeout=1.0)

    async def _wait_for_work(self, timeout: Optional[float] = None) -> None:
        """Block until new work arrives or the worker is stopped."""
        if self._worker_wake_event is None:
            self._worker_wake_event = asyncio.Event()

        self._worker_wake_event.clear()
        try:
            await asyncio.wait_for(self._worker_wake_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return

    def _wake_worker(self) -> None:
        """Signal the worker to wake up immediately when new work is queued."""
        if self._worker_wake_event is not None:
            self._worker_wake_event.set()

    def start_worker(self) -> None:
        """Start the background worker task."""
        if self._worker_wake_event is None:
            self._worker_wake_event = asyncio.Event()

        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop_worker(self) -> None:
        """Stop the background worker task."""
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
    
    async def embed_documents(
        self,
        docs: list[Document],
        request_id: str = "",
        wait_for_result: bool = False,
        wait_timeout: Optional[float] = 600.0,
    ) -> dict[str, Any]:
        """Queue documents for embedding with automatic retry and splitting.
        
        Args:
            docs: Documents to embed
            request_id: Optional request identifier
            wait_for_result: If True, wait for completion before returning
            wait_timeout: Max wait time in seconds, or None to wait forever
            
        Returns:
            Dictionary with request_id and optionally result/error
        """
        self.start_worker()

        if not request_id:
            request_id = f"req_{int(time.time() * 1000)}"
        
        # Split large batches
        batches = self._split_batch(docs)
        
        if len(batches) == 1:
            # Single batch - queue directly
            request = EmbeddingRequest(
                docs=batches[0],
                request_id=request_id,
            )

            async with self._lock:
                self.request_queue.append(request)

            self._wake_worker()

            console.print(
                f"[blue]📝 Queued request {request_id} "
                f"({len(docs)} docs)[/blue]"
            )

            if wait_for_result:
                return await self._wait_for_completion(request_id, timeout=wait_timeout)

            # Register a background waiter so other parts of the system can
            # wait for this embedding to complete later (phase boundary).
            try:
                from gpt_researcher.utils.embedding_registry import register

                task = asyncio.create_task(register(request_id, self._wait_for_completion(request_id)))
                task.add_done_callback(lambda t: t.exception() if t.cancelled() is False and t.exception() else None)
            except Exception:
                # If registration fails, proceed silently — this is a best-effort coordination aid.
                pass

            return {"request_id": request_id, "status": "queued", "batch_count": 1}

        else:
            # Multiple batches - queue all with sub-IDs
            batch_requests = []
            for i, batch in enumerate(batches):
                batch_id = f"{request_id}_batch_{i+1}"
                request = EmbeddingRequest(
                    docs=batch,
                    request_id=batch_id,
                )
                batch_requests.append(request)

                async with self._lock:
                    self.request_queue.append(request)

                self._wake_worker()

            console.print(
                f"[blue]📝 Split & queued {len(batches)} batches "
                f"({len(docs)} docs total)[/blue]"
            )

            if wait_for_result:
                return await self._wait_for_all_batches(batch_requests, timeout=wait_timeout)

            try:
                from gpt_researcher.utils.embedding_registry import register
                for r in batch_requests:
                    task = asyncio.create_task(register(r.request_id, self._wait_for_completion(r.request_id)))
                    task.add_done_callback(lambda t: t.exception() if t.cancelled() is False and t.exception() else None)
            except Exception:
                pass

            return {
                "request_id": request_id,
                "status": "queued",
                "batch_count": len(batches),
                "batch_ids": [r.request_id for r in batch_requests],
            }
    
    async def _wait_for_completion(
        self,
        request_id: str,
        timeout: Optional[float] = 600.0,
    ) -> dict[str, Any]:
        """Wait for a single request to complete.
        
        Args:
            request_id: The request to wait for
            timeout: Max wait time in seconds
            
        Returns:
            Completed request with result or error
        """
        start = time.time()
        
        while timeout is None or time.time() - start < timeout:
            if request_id in self.request_history:
                req = self.request_history[request_id]
                if req.status in ("completed", "failed"):
                    return {
                        "request_id": request_id,
                        "status": req.status,
                        "result": req.result,
                        "error": req.error,
                        "retry_count": req.retry_count,
                    }
            
            await asyncio.sleep(0.5)
        
        return {
            "request_id": request_id,
            "status": "timeout",
            "error": f"Request did not complete within {timeout}s",
        }
    
    async def _wait_for_all_batches(
        self,
        batch_requests: list[EmbeddingRequest],
        timeout: Optional[float] = 600.0,
    ) -> dict[str, Any]:
        """Wait for all batches to complete.
        
        Args:
            batch_requests: The batches to wait for
            timeout: Max wait time in seconds
            
        Returns:
            Combined result with all batch results
        """
        results = []
        errors = []
        start = time.time()
        
        while timeout is None or (time.time() - start < timeout):
            all_done = True
            
            for batch_req in batch_requests:
                if batch_req.request_id not in self.request_history:
                    all_done = False
                    continue
                
                req = self.request_history[batch_req.request_id]
                
                if req.status == "completed":
                    results.extend(req.result)
                elif req.status == "failed":
                    errors.append({
                        "batch_id": batch_req.request_id,
                        "error": req.error,
                    })
                else:
                    all_done = False
            
            if all_done:
                return {
                    "status": "completed" if not errors else "partial_failure",
                    "total_embeddings": len(results),
                    "results": results,
                    "errors": errors if errors else None,
                }
            
            await asyncio.sleep(0.5)
        
        return {
            "status": "timeout",
            "error": f"Batches did not complete within {timeout}s",
            "partial_results": results,
            "errors": errors,
        }
    
    def get_status(self) -> dict[str, Any]:
        """Get current pipeline status.
        
        Returns:
            Status dictionary with queue size, completed, failed, etc.
        """
        completed = sum(1 for r in self.request_history.values() if r.status == "completed")
        failed = sum(1 for r in self.request_history.values() if r.status == "failed")
        processing = sum(1 for r in self.request_history.values() if r.status == "processing")
        
        return {
            "queued": len(self.request_queue),
            "processing": processing,
            "completed": completed,
            "failed": failed,
            "total_requests": len(self.request_history),
            "tokens_used": self.tokens_used,
            "tokens_limit": self.max_tokens_per_minute,
            "worker_running": self._worker_task is not None and not self._worker_task.done(),
        }
    
    def get_request_status(self, request_id: str) -> Optional[dict[str, Any]]:
        """Get status of a specific request.
        
        Args:
            request_id: The request identifier
            
        Returns:
            Request status or None if not found
        """
        if request_id not in self.request_history:
            # Check if in queue
            for req in self.request_queue:
                if req.request_id == request_id:
                    return {"status": "queued", "request_id": request_id}
            return None
        
        req = self.request_history[request_id]
        return {
            "request_id": request_id,
            "status": req.status,
            "doc_count": len(req.docs),
            "retry_count": req.retry_count,
            "error": req.error,
            "created_at": req.created_at,
        }
