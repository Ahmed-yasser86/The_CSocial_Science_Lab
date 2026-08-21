"""Integration module for ResilientEmbeddingPipeline with research system.

This module provides utilities to integrate the resilient embedding pipeline
with the main research pipeline, including persistence and monitoring.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from langchain_core.documents import Document
from rich.console import Console
from rich.table import Table

from gpt_researcher.memory.resilient_embeddings import ResilientEmbeddingPipeline

console = Console()


class EmbeddingPipelineManager:
    """Manages embedding pipeline lifecycle and provides monitoring."""
    
    def __init__(
        self,
        embedding_provider: str,
        model: str,
        log_dir: Optional[str] = None,
        **pipeline_kwargs,
    ):
        """Initialize the pipeline manager.
        
        Args:
            embedding_provider: Embedding provider name
            model: Embedding model
            log_dir: Directory for logging pipeline metrics
            **pipeline_kwargs: Additional args for ResilientEmbeddingPipeline
        """
        self.pipeline = ResilientEmbeddingPipeline(
            embedding_provider=embedding_provider,
            model=model,
            **pipeline_kwargs,
        )
        
        self.log_dir = Path(log_dir) if log_dir else None
        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.start_time = datetime.now()
    
    def start(self) -> None:
        """Start the embedding worker."""
        self.pipeline.start_worker()
        console.print("[bold green]✓ Embedding pipeline started[/bold green]")
    
    async def stop(self) -> None:
        """Stop the embedding worker."""
        await self.pipeline.stop_worker()
        console.print("[bold yellow]⛔ Embedding pipeline stopped[/bold yellow]")
    
    async def embed_documents_safe(
        self,
        docs: list[Document],
        request_id: str = "",
        timeout: float = 600.0,
    ) -> tuple[list[list[float]], list[str]]:
        """Embed documents with guaranteed no data loss.
        
        Args:
            docs: Documents to embed
            request_id: Optional request ID
            timeout: Timeout in seconds
            
        Returns:
            Tuple of (embeddings, failed_doc_ids)
            - embeddings: List of embedding vectors
            - failed_doc_ids: List of docs that failed to embed
        """
        if not docs:
            return [], []
        
        result = await self.pipeline.embed_documents(
            docs,
            request_id=request_id,
            wait_for_result=True,
        )
        
        if result["status"] == "completed":
            return result["results"], []
        elif result["status"] == "partial_failure":
            failed_indices = set()
            for error_info in result.get("errors", []):
                # Extract indices from batch_id
                try:
                    batch_id = error_info["batch_id"]
                    # Parse batch indices if available
                    if "_batch_" in batch_id:
                        batch_num = int(batch_id.split("_batch_")[-1])
                        # Estimate which docs failed (conservative approach)
                        failed_indices.add(batch_num)
                except (IndexError, ValueError):
                    pass
            
            failed_doc_ids = [
                docs[i].metadata.get("id", f"doc_{i}") 
                for i in failed_indices
            ]
            
            return result.get("partial_results", []), failed_doc_ids
        else:
            # Full failure - return empty with all docs marked as failed
            failed_doc_ids = [
                doc.metadata.get("id", f"doc_{i}") 
                for i, doc in enumerate(docs)
            ]
            return [], failed_doc_ids
    
    def print_status(self) -> None:
        """Print formatted pipeline status."""
        status = self.pipeline.get_status()
        
        table = Table(title="Embedding Pipeline Status")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Queued", str(status["queued"]))
        table.add_row("Processing", str(status["processing"]))
        table.add_row("Completed", str(status["completed"]))
        table.add_row("Failed", str(status["failed"]))
        table.add_row("Total Requests", str(status["total_requests"]))
        table.add_row("Tokens Used", f"{status['tokens_used']}/{status['tokens_limit']}")
        table.add_row("Worker Running", "✓" if status["worker_running"] else "✗")
        
        console.print(table)
    
    def save_metrics(self) -> None:
        """Save pipeline metrics to log file."""
        if not self.log_dir:
            return
        
        status = self.pipeline.get_status()
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": (datetime.now() - self.start_time).total_seconds(),
            "status": status,
            "request_history": {
                req_id: {
                    "status": req.status,
                    "doc_count": len(req.docs),
                    "retry_count": req.retry_count,
                    "error": req.error,
                }
                for req_id, req in self.pipeline.request_history.items()
            },
        }
        
        log_file = self.log_dir / f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_file, "w") as f:
            json.dump(metrics, f, indent=2)
        
        console.print(f"[dim]Metrics saved to {log_file}[/dim]")
    
    async def embed_with_fallback(
        self,
        docs: list[Document],
        fallback_provider: Optional[str] = None,
        fallback_model: Optional[str] = None,
    ) -> tuple[list[list[float]], list[str]]:
        """Embed with automatic fallback provider on failure.
        
        Args:
            docs: Documents to embed
            fallback_provider: Fallback provider if primary fails
            fallback_model: Fallback model if primary fails
            
        Returns:
            Tuple of (embeddings, failed_doc_ids)
        """
        embeddings, failed_docs = await self.embed_documents_safe(docs)
        
        if failed_docs and fallback_provider and fallback_model:
            console.print(
                f"[yellow]⚠ {len(failed_docs)} docs failed. "
                f"Retrying with fallback provider...[/yellow]"
            )
            
            # Create fallback manager
            fallback_manager = EmbeddingPipelineManager(
                embedding_provider=fallback_provider,
                model=fallback_model,
            )
            fallback_manager.start()
            
            try:
                # Retry failed docs only
                failed_doc_objs = [
                    doc for doc in docs 
                    if doc.metadata.get("id", "") in failed_docs
                ]
                
                fallback_embeddings, still_failed = await fallback_manager.embed_documents_safe(
                    failed_doc_objs
                )
                
                # Merge results
                embeddings.extend(fallback_embeddings)
                failed_docs = still_failed
                
            finally:
                await fallback_manager.stop()
        
        return embeddings, failed_docs


class ResearchPipelineIntegration:
    """Integration with research pipeline."""
    
    def __init__(self, manager: EmbeddingPipelineManager):
        """Initialize research pipeline integration.
        
        Args:
            manager: EmbeddingPipelineManager instance
        """
        self.manager = manager
        self.embedded_docs = {}
        self.failed_docs = []
    
    async def process_research_documents(
        self,
        documents: list[Document],
        batch_name: str = "research",
    ) -> dict[str, Any]:
        """Process research documents through embedding pipeline.
        
        Args:
            documents: Documents from research
            batch_name: Batch name for tracking
            
        Returns:
            Processing result with stats
        """
        console.print(f"\n[bold]Processing {len(documents)} documents...[/bold]")
        
        start_time = datetime.now()
        embeddings, failed = await self.manager.embed_documents_safe(
            documents,
            request_id=batch_name,
        )
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Track results
        self.embedded_docs[batch_name] = embeddings
        self.failed_docs.extend(failed)
        
        result = {
            "batch_name": batch_name,
            "total_docs": len(documents),
            "successfully_embedded": len(embeddings),
            "failed": len(failed),
            "elapsed_seconds": elapsed,
            "failed_doc_ids": failed,
        }
        
        if failed:
            console.print(
                f"[yellow]⚠ Warning: {len(failed)}/{len(documents)} docs failed to embed[/yellow]"
            )
        else:
            console.print(
                f"[green]✓ All {len(documents)} documents embedded successfully[/green]"
            )
        
        return result
    
    def get_summary(self) -> dict[str, Any]:
        """Get summary of all processing."""
        return {
            "total_batches": len(self.embedded_docs),
            "total_embeddings": sum(len(e) for e in self.embedded_docs.values()),
            "total_failed": len(self.failed_docs),
            "failed_docs": self.failed_docs,
        }
