"""Example usage of the ResilientEmbeddingPipeline.

This demonstrates how to use the robust embedding pipeline with:
- Rate limiting
- Queue-based processing
- Automatic retry with backoff
- Large batch splitting
- Zero data loss
"""

import asyncio
from langchain_core.documents import Document

from gpt_researcher.memory.resilient_embeddings import ResilientEmbeddingPipeline


async def main():
    """Example: Process documents through resilient embedding pipeline."""
    
    # Initialize pipeline
    pipeline = ResilientEmbeddingPipeline(
        embedding_provider="openai",  # or your provider
        model="text-embedding-3-small",
        max_tokens_per_minute=90000,
        chunk_size=512,
        max_retries=3,
    )
    
    # Start worker
    pipeline.start_worker()
    
    try:
        # Example 1: Single request (small batch)
        small_docs = [
            Document(page_content="Document 1: Hello world"),
            Document(page_content="Document 2: Another test"),
        ]
        
        result = await pipeline.embed_documents(
            small_docs,
            request_id="small_batch",
            wait_for_result=True,
        )
        print(f"Small batch result: {result}")
        
        # Example 2: Large batch (auto-split)
        large_docs = [
            Document(page_content=f"Document {i}: " + "Lorem ipsum dolor sit amet " * 100)
            for i in range(1000)
        ]
        
        result = await pipeline.embed_documents(
            large_docs,
            request_id="large_batch",
            wait_for_result=True,
        )
        print(f"Large batch result: {result}")
        
        # Example 3: Multiple requests (async)
        tasks = []
        for batch_num in range(5):
            docs = [
                Document(page_content=f"Batch {batch_num}, Doc {i}: Test content")
                for i in range(10)
            ]
            task = pipeline.embed_documents(
                docs,
                request_id=f"batch_{batch_num}",
                wait_for_result=True,
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        print(f"Multiple batches completed: {len(results)} batches processed")
        
        # Check final status
        status = pipeline.get_status()
        print(f"\nFinal status: {status}")
        
    finally:
        # Stop worker gracefully
        await pipeline.stop_worker()


async def research_pipeline_example():
    """Example: Using in a research pipeline with error handling."""
    
    pipeline = ResilientEmbeddingPipeline(
        embedding_provider="openai",
        model="text-embedding-3-small",
        max_tokens_per_minute=90000,
        chunk_size=256,
        max_retries=5,  # Higher for important pipeline
    )
    
    pipeline.start_worker()
    
    try:
        # Simulate research documents
        research_docs = [
            Document(page_content=f"Research paper {i}: Abstract on topic X"),
            Document(page_content=f"Research paper {i}: Introduction"),
            Document(page_content=f"Research paper {i}: Methodology"),
            Document(page_content=f"Research paper {i}: Results"),
            Document(page_content=f"Research paper {i}: Conclusion"),
        ]
        
        # Queue all at once (worker processes asynchronously)
        result = await pipeline.embed_documents(
            research_docs,
            request_id="research_set_1",
            wait_for_result=True,  # Wait until all complete
        )
        
        if result["status"] == "completed":
            print(f"✓ Successfully embedded {result['total_embeddings']} documents")
        elif result["status"] == "partial_failure":
            print(f"⚠ Partial success: {result['total_embeddings']} docs, "
                  f"{len(result['errors'])} batches failed")
            for error in result["errors"]:
                print(f"  Failed batch: {error['batch_id']} - {error['error']}")
        else:
            print(f"✗ Request failed: {result.get('error')}")
        
    finally:
        await pipeline.stop_worker()


if __name__ == "__main__":
    # Run basic example
    asyncio.run(main())
    
    # Or run research pipeline example
    # asyncio.run(research_pipeline_example())
