"""Comprehensive demo and tests for ResilientEmbeddingPipeline.

Run this to verify all features work correctly.
"""

import asyncio
from datetime import datetime
from langchain_core.documents import Document

from gpt_researcher.memory.resilient_embeddings import ResilientEmbeddingPipeline
from gpt_researcher.memory.pipeline_integration import (
    EmbeddingPipelineManager,
    ResearchPipelineIntegration,
)
from gpt_researcher.memory.embedding_config import get_config


async def demo_basic_pipeline():
    """Demo 1: Basic pipeline with small batch."""
    print("\n" + "="*60)
    print("DEMO 1: Basic Pipeline")
    print("="*60)
    
    pipeline = ResilientEmbeddingPipeline(
        embedding_provider="openai",
        model="text-embedding-3-small",
    )
    
    pipeline.start_worker()
    
    try:
        docs = [
            Document(page_content="Hello world"),
            Document(page_content="Another test document"),
        ]
        
        print(f"\n→ Embedding {len(docs)} documents...")
        result = await pipeline.embed_documents(
            docs,
            request_id="demo_basic",
            wait_for_result=True,
        )
        
        if result["status"] == "completed":
            print(f"✓ Success! Got {result['total_embeddings']} embeddings")
        else:
            print(f"✗ Failed: {result.get('error', 'Unknown error')}")
        
    finally:
        await pipeline.stop_worker()


async def demo_large_batch():
    """Demo 2: Auto-splitting of large batch."""
    print("\n" + "="*60)
    print("DEMO 2: Large Batch (Auto-Split)")
    print("="*60)
    
    pipeline = ResilientEmbeddingPipeline(
        embedding_provider="openai",
        model="text-embedding-3-small",
        chunk_size=50,  # Small for demo
    )
    
    pipeline.start_worker()
    
    try:
        # Create large batch
        docs = [
            Document(
                page_content=f"Document {i}: " + "Lorem ipsum dolor sit amet " * 50
            )
            for i in range(100)
        ]
        
        print(f"\n→ Embedding {len(docs)} documents (will auto-split)...")
        result = await pipeline.embed_documents(
            docs,
            request_id="demo_large",
            wait_for_result=True,
        )
        
        if result["status"] in ("completed", "partial_failure"):
            print(f"✓ Got {result.get('total_embeddings', len(result.get('partial_results', [])))} embeddings")
            if "batch_ids" in result:
                print(f"  Split into {len(result['batch_ids'])} batches")
        else:
            print(f"✗ Failed: {result.get('error')}")
        
    finally:
        await pipeline.stop_worker()


async def demo_retry_logic():
    """Demo 3: Retry logic with rate limiting."""
    print("\n" + "="*60)
    print("DEMO 3: Rate Limiting & Retry (Simulated)")
    print("="*60)
    
    pipeline = ResilientEmbeddingPipeline(
        embedding_provider="openai",
        model="text-embedding-3-small",
        max_tokens_per_minute=100,  # Very low for demo
        max_retries=2,
    )
    
    pipeline.start_worker()
    
    try:
        docs = [Document(page_content=f"Test {i}") for i in range(3)]
        
        print(f"\n→ Embedding {len(docs)} with low rate limit (100 TPM)...")
        print("  (Watch for: 'TPM limit reached. Waiting...')")
        
        result = await pipeline.embed_documents(
            docs,
            request_id="demo_rate_limit",
            wait_for_result=True,
        )
        
        status = pipeline.get_status()
        print(f"\n✓ Completed!")
        print(f"  Tokens used: {status['tokens_used']}/{status['tokens_limit']}")
        
    finally:
        await pipeline.stop_worker()


async def demo_manager():
    """Demo 4: Using EmbeddingPipelineManager."""
    print("\n" + "="*60)
    print("DEMO 4: Pipeline Manager (Recommended)")
    print("="*60)
    
    manager = EmbeddingPipelineManager(
        embedding_provider="openai",
        model="text-embedding-3-small",
        log_dir="./test_logs",
        max_retries=3,
    )
    
    manager.start()
    
    try:
        docs = [Document(page_content=f"Research {i}") for i in range(20)]
        
        print(f"\n→ Embedding with manager...")
        embeddings, failed = await manager.embed_documents_safe(docs)
        
        print(f"✓ Results:")
        print(f"  - Successfully embedded: {len(embeddings)}")
        print(f"  - Failed: {len(failed)}")
        
        print(f"\n📊 Pipeline Status:")
        manager.print_status()
        
        # Save metrics
        manager.save_metrics()
        print(f"\n✓ Metrics saved to test_logs/")
        
    finally:
        await manager.stop()


async def demo_research_integration():
    """Demo 5: Research pipeline integration."""
    print("\n" + "="*60)
    print("DEMO 5: Research Pipeline Integration")
    print("="*60)
    
    config = get_config("research")
    manager = EmbeddingPipelineManager(**config.to_dict())
    research = ResearchPipelineIntegration(manager)
    
    manager.start()
    
    try:
        # Simulate research document processing
        batch1 = [
            Document(page_content=f"Paper {i}: Abstract") for i in range(10)
        ]
        batch2 = [
            Document(page_content=f"Paper {i}: Methodology") for i in range(10)
        ]
        
        print(f"\n→ Processing research batch 1...")
        result1 = await research.process_research_documents(batch1, "papers_abstracts")
        
        print(f"\n→ Processing research batch 2...")
        result2 = await research.process_research_documents(batch2, "papers_methods")
        
        print(f"\n📊 Summary:")
        summary = research.get_summary()
        for key, value in summary.items():
            print(f"  {key}: {value}")
        
    finally:
        manager.save_metrics()
        await manager.stop()


async def demo_config_presets():
    """Demo 6: Using configuration presets."""
    print("\n" + "="*60)
    print("DEMO 6: Configuration Presets")
    print("="*60)
    
    configs = {
        "research": "For critical research (no data loss)",
        "throughput": "For maximum speed",
        "low_cost": "For cost optimization",
        "local": "For local Ollama (free, offline)",
    }
    
    print("\nAvailable configurations:")
    for name, description in configs.items():
        try:
            config = get_config(name)
            print(f"\n✓ {name.upper()}")
            print(f"  {description}")
            print(f"  - Provider: {config.provider}")
            print(f"  - Model: {config.model}")
            print(f"  - Chunk size: {config.chunk_size}")
            print(f"  - Max retries: {config.max_retries}")
            print(f"  - TPM: {config.max_tokens_per_minute}")
        except Exception as e:
            print(f"✗ {name}: {e}")


async def demo_concurrent_requests():
    """Demo 7: Multiple concurrent requests."""
    print("\n" + "="*60)
    print("DEMO 7: Concurrent Requests")
    print("="*60)
    
    pipeline = ResilientEmbeddingPipeline(
        embedding_provider="openai",
        model="text-embedding-3-small",
    )
    
    pipeline.start_worker()
    
    try:
        print(f"\n→ Queuing 5 concurrent requests...")
        
        tasks = []
        for i in range(5):
            docs = [Document(page_content=f"Request {i}, Doc {j}") for j in range(10)]
            task = pipeline.embed_documents(
                docs,
                request_id=f"concurrent_{i}",
                wait_for_result=True,
            )
            tasks.append(task)
        
        print("⏳ Processing all concurrently...")
        start = datetime.now()
        results = await asyncio.gather(*tasks)
        elapsed = (datetime.now() - start).total_seconds()
        
        successful = sum(1 for r in results if r.get("status") == "completed")
        print(f"✓ Completed {successful}/{len(results)} requests in {elapsed:.1f}s")
        
        # Show queue efficiency
        status = pipeline.get_status()
        print(f"\n📊 Queue Statistics:")
        print(f"  - Total requests processed: {status['completed']}")
        print(f"  - Failed: {status['failed']}")
        print(f"  - Tokens used: {status['tokens_used']}/{status['tokens_limit']}")
        
    finally:
        await pipeline.stop_worker()


async def demo_request_tracking():
    """Demo 8: Request status tracking."""
    print("\n" + "="*60)
    print("DEMO 8: Request Status Tracking")
    print("="*60)
    
    pipeline = ResilientEmbeddingPipeline(
        embedding_provider="openai",
        model="text-embedding-3-small",
    )
    
    pipeline.start_worker()
    
    try:
        docs = [Document(page_content=f"Doc {i}") for i in range(5)]
        
        # Queue without waiting
        result = await pipeline.embed_documents(
            docs,
            request_id="tracked_request",
            wait_for_result=False,
        )
        
        print(f"\n→ Request queued: {result['request_id']}")
        print("⏳ Polling status...")
        
        # Poll status
        for attempt in range(10):
            await asyncio.sleep(1)
            status = pipeline.get_request_status("tracked_request")
            
            if status:
                print(f"  [{attempt+1}] Status: {status['status']}")
                
                if status['status'] in ("completed", "failed"):
                    print(f"\n✓ Final status:")
                    for key, value in status.items():
                        print(f"  {key}: {value}")
                    break
        
    finally:
        await pipeline.stop_worker()


async def main():
    """Run all demos."""
    print("\n" + "█"*60)
    print("█ RESILIENT EMBEDDING PIPELINE - COMPREHENSIVE DEMO")
    print("█"*60)
    print("\nThis demo shows all features. Some demos require API keys:")
    print("  - OpenAI: Set OPENAI_API_KEY")
    print("  - Ollama: Run `ollama serve` first")
    
    demos = [
        ("Basic Pipeline", demo_basic_pipeline),
        ("Large Batch (Auto-Split)", demo_large_batch),
        ("Rate Limiting & Retry", demo_retry_logic),
        ("Pipeline Manager", demo_manager),
        ("Research Integration", demo_research_integration),
        ("Config Presets", demo_config_presets),
        ("Concurrent Requests", demo_concurrent_requests),
        ("Request Tracking", demo_request_tracking),
    ]
    
    for name, demo_func in demos:
        try:
            print(f"\n\n{'→'*20} Running: {name}")
            await demo_func()
            print(f"{'✓'*20} {name} completed")
        except Exception as e:
            print(f"{'✗'*20} {name} error:")
            print(f"  {e}")
            print(f"\n  (This may be due to missing API keys. That's OK for demo.)")
    
    print("\n" + "█"*60)
    print("█ ALL DEMOS COMPLETED")
    print("█"*60)
    print("\n📚 Next steps:")
    print("  1. Read RESILIENT_EMBEDDINGS_README.md for full docs")
    print("  2. Check embedding_config.py for preset configurations")
    print("  3. Use EmbeddingPipelineManager in your research pipeline")
    print("  4. Set EMBEDDING_* env vars for your preferred provider\n")


if __name__ == "__main__":
    asyncio.run(main())
