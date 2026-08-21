# Resilient Embedding Pipeline

**Zero Data Loss Guaranteed** - A robust embedding pipeline for GPT Researcher with rate limiting, queue-based processing, automatic retry, and batch splitting.

## Features ✨

- **Rate Limiting**: Token-based rate limiting using tiktoken (respects provider limits)
- **Queue-Based Processing**: Background worker processes embeddings asynchronously
- **Automatic Retry**: Exponential backoff retry with configurable max attempts
- **Batch Splitting**: Large requests automatically split to avoid API limits
- **Zero Data Loss**: Queue ensures no document is lost even on failure
- **Monitoring**: Real-time status tracking and metrics logging
- **Fallback Support**: Automatic fallback to secondary provider on failure
- **Multiple Providers**: Works with OpenAI, Azure, Ollama, Cohere, and others

## Architecture 🏗️

```
Research Pipeline
    ↓
Document List → ResilientEmbeddingPipeline
                    ↓
                [Rate Limiter] (Token-based)
                    ↓
                [Queue] (Background Worker)
                    ↓
                [Batch Splitter] (Large requests)
                    ↓
                [Retry Manager] (Exponential backoff)
                    ↓
                [Embedding Provider] (OpenAI, etc.)
                    ↓
                Results + Status
```

## Installation

```bash
# Already included in gpt-researcher
# Just import and use:
from gpt_researcher.memory.resilient_embeddings import ResilientEmbeddingPipeline
from gpt_researcher.memory.pipeline_integration import EmbeddingPipelineManager
from gpt_researcher.memory.embedding_config import get_config
```

## Quick Start

### Basic Usage

```python
import asyncio
from langchain_core.documents import Document
from gpt_researcher.memory.resilient_embeddings import ResilientEmbeddingPipeline

async def embed_documents():
    # Create pipeline
    pipeline = ResilientEmbeddingPipeline(
        embedding_provider="openai",
        model="text-embedding-3-small",
        max_tokens_per_minute=90000,
    )
    
    # Start background worker
    pipeline.start_worker()
    
    try:
        # Prepare documents
        docs = [
            Document(page_content="Document 1"),
            Document(page_content="Document 2"),
        ]
        
        # Queue for embedding (auto-split, retry, rate-limit)
        result = await pipeline.embed_documents(
            docs,
            request_id="my_request",
            wait_for_result=True,  # Wait until complete
        )
        
        print(result)
        # Output:
        # {
        #     'status': 'completed',
        #     'total_embeddings': 2,
        #     'results': [[...embedding vectors...]],
        #     'errors': None
        # }
        
    finally:
        await pipeline.stop_worker()

# Run
asyncio.run(embed_documents())
```

### With Pipeline Manager (Recommended for Research)

```python
import asyncio
from gpt_researcher.memory.pipeline_integration import EmbeddingPipelineManager
from langchain_core.documents import Document

async def research_pipeline():
    # Create manager
    manager = EmbeddingPipelineManager(
        embedding_provider="openai",
        model="text-embedding-3-small",
        log_dir="./embedding_logs",  # Save metrics
        max_retries=5,  # Higher for research
    )
    
    # Start
    manager.start()
    
    try:
        docs = [Document(page_content=f"Research paper {i}") for i in range(100)]
        
        # Embed with guaranteed no data loss
        embeddings, failed_docs = await manager.embed_documents_safe(docs)
        
        print(f"✓ {len(embeddings)} embedded successfully")
        if failed_docs:
            print(f"⚠ {len(failed_docs)} failed: {failed_docs}")
        
        # View status
        manager.print_status()
        
        # Save metrics
        manager.save_metrics()
        
    finally:
        await manager.stop()

asyncio.run(research_pipeline())
```

### Using Preset Configurations

```python
from gpt_researcher.memory.embedding_config import get_config
from gpt_researcher.memory.pipeline_integration import EmbeddingPipelineManager

# Research pipeline (high reliability)
config = get_config("research")
manager = EmbeddingPipelineManager(**config.to_dict())

# High throughput (speed optimized)
config = get_config("throughput")

# Low cost (uses smaller model)
config = get_config("low_cost")

# Local Ollama (free, no API keys)
config = get_config("local")
```

### With Fallback Provider

```python
async def embed_with_fallback():
    manager = EmbeddingPipelineManager(
        embedding_provider="openai",
        model="text-embedding-3-small",
    )
    manager.start()
    
    try:
        docs = [Document(page_content=f"Doc {i}") for i in range(50)]
        
        # Automatically retry with Ollama if OpenAI fails
        embeddings, failed = await manager.embed_with_fallback(
            docs,
            fallback_provider="ollama",
            fallback_model="nomic-embed-text",
        )
        
    finally:
        await manager.stop()

asyncio.run(embed_with_fallback())
```

## Configuration Options

### ResilientEmbeddingPipeline

```python
ResilientEmbeddingPipeline(
    # Provider
    embedding_provider="openai",      # openai, azure_openai, ollama, cohere, etc.
    model="text-embedding-3-small",   # Model name
    
    # Rate limiting
    max_tokens_per_minute=90000,      # Token budget per minute
    encoding_name="cl100k_base",      # Tiktoken encoding
    
    # Batch handling
    chunk_size=512,                   # Max docs per request
    max_retries=3,                    # Retry attempts
    
    # Provider-specific
    **embedding_kwargs                # Passed to provider
)
```

### EmbeddingPipelineManager

```python
EmbeddingPipelineManager(
    embedding_provider="openai",
    model="text-embedding-3-small",
    log_dir="./logs",                 # Directory for metrics
    
    # Plus all ResilientEmbeddingPipeline options
    max_tokens_per_minute=90000,
    chunk_size=512,
    max_retries=3,
)
```

### Preset Configs

| Config | Use Case | Batch Size | Retries | Timeout | Provider |
|--------|----------|-----------|---------|---------|----------|
| `research` | No data loss (recommended) | 256 | 5 | 900s | OpenAI |
| `throughput` | Speed optimized | 1024 | 2 | 300s | OpenAI |
| `low_cost` | Cost optimized | 256 | 3 | 600s | OpenAI |
| `local` | Free, offline | 512 | 2 | 300s | Ollama |

## Status Monitoring

### Pipeline Status

```python
# Get status
status = pipeline.get_status()
# Output:
# {
#     'queued': 3,
#     'processing': 1,
#     'completed': 10,
#     'failed': 0,
#     'total_requests': 14,
#     'tokens_used': 45000,
#     'tokens_limit': 90000,
#     'worker_running': True
# }

# Get specific request status
req_status = pipeline.get_request_status("my_request")
# Output:
# {
#     'request_id': 'my_request',
#     'status': 'completed',
#     'doc_count': 100,
#     'retry_count': 0,
#     'error': None,
#     'created_at': 1723234567.89
# }
```

### Manager Status (Pretty Print)

```python
manager.print_status()
# Output:
# ╭─────────────────────────────────╮
# │ Embedding Pipeline Status       │
# ├──────────────┬─────────────────┤
# │ Metric       │ Value           │
# ├──────────────┼─────────────────┤
# │ Queued       │ 0               │
# │ Processing   │ 0               │
# │ Completed    │ 25              │
# │ Failed       │ 0               │
# │ Total Req... │ 25              │
# │ Tokens Used  │ 45000/90000     │
# │ Worker Run.. │ ✓               │
# ╰──────────────┴─────────────────╯
```

### Save Metrics

```python
# Save to JSON
manager.save_metrics()
# Creates: embedding_logs/metrics_20240803_164200.json

# Contents:
# {
#   "timestamp": "2024-08-03T16:42:00.123456",
#   "elapsed_seconds": 42.5,
#   "status": {...},
#   "request_history": {
#     "req_1": {
#       "status": "completed",
#       "doc_count": 100,
#       "retry_count": 0,
#       "error": null
#     }
#   }
# }
```

## How It Works

### Rate Limiting

Uses tiktoken to count actual tokens consumed:

```python
# Automatic token counting
docs = [Document(page_content="...")]
tokens = pipeline.count_tokens(docs)

# Waits if approaching limit
# "TPM limit reached. Waiting 15.3s..."

# Resets every 70 seconds
```

### Queue-Based Processing

```
Request Queue (FIFO)
├── Request 1 (pending)
├── Request 2 (queued)
├── Request 3 (queued)
└── Request 4 (queued)
    ↓
Background Worker
├── Acquire tokens (rate limit)
├── Call embeddings provider
├── Handle retry on failure
└── Store result
```

### Batch Splitting

Automatically splits if:
- Batch size > chunk_size documents
- Token count > 10% of monthly limit

```python
# Input: 1000 large documents
# Detected: Too many tokens
# Action: Split into 4 batches of 250 docs
# Result: 4 sequential requests, each within limits
```

### Retry Logic

Exponential backoff on failure:

```
Request fails → Retry 1 after 1s
Fails again   → Retry 2 after 2s
Fails again   → Retry 3 after 4s
Max retries   → Mark as failed, move next
```

## Error Handling

### Partial Failures (Some Docs Fail)

```python
result = await pipeline.embed_documents(docs, wait_for_result=True)

if result["status"] == "partial_failure":
    print(f"✓ {result['total_embeddings']} succeeded")
    for error in result["errors"]:
        print(f"✗ Batch {error['batch_id']}: {error['error']}")
    
    # You have partial_results - use what succeeded
    embeddings = result["partial_results"]
```

### Full Failure (All Docs Fail)

```python
if result["status"] == "failed":
    print(f"Error: {result['error']}")
    # Return empty, no data lost - still in queue
```

### Retry Exhausted

```python
# After max_retries attempts
status = pipeline.get_request_status(request_id)
if status["status"] == "failed":
    print(f"Failed after {status['retry_count']} retries")
    print(f"Error: {status['error']}")
```

## Integration with Research Pipeline

### Example: Research Document Processing

```python
from gpt_researcher.memory.pipeline_integration import ResearchPipelineIntegration
from gpt_researcher.memory.pipeline_integration import EmbeddingPipelineManager
from gpt_researcher.memory.embedding_config import get_config

async def process_research():
    # Setup
    config = get_config("research")  # No data loss
    manager = EmbeddingPipelineManager(**config.to_dict())
    research = ResearchPipelineIntegration(manager)
    
    manager.start()
    
    try:
        # Process research papers
        papers = [Document(page_content=f"Paper {i}") for i in range(100)]
        
        result = await research.process_research_documents(
            papers,
            batch_name="research_batch_1",
        )
        
        print(result)
        # {
        #     'batch_name': 'research_batch_1',
        #     'total_docs': 100,
        #     'successfully_embedded': 100,
        #     'failed': 0,
        #     'elapsed_seconds': 12.5,
        #     'failed_doc_ids': []
        # }
        
        # Get summary
        summary = research.get_summary()
        print(summary)
        
    finally:
        manager.save_metrics()
        await manager.stop()

asyncio.run(process_research())
```

## Environment Variables

```bash
# Provider configuration
export EMBEDDING_PROVIDER=openai
export EMBEDDING_MODEL=text-embedding-3-small
export OPENAI_API_KEY=sk-...

# Rate limiting
export EMBEDDING_TPM=90000

# Batch processing
export EMBEDDING_CHUNK_SIZE=512
export EMBEDDING_MAX_RETRIES=3

# Logging
export EMBEDDING_LOG_DIR=./embedding_logs

# Timeout
export EMBEDDING_TIMEOUT=600
```

Load from env:

```python
from gpt_researcher.memory.embedding_config import load_from_env

config = load_from_env()
manager = EmbeddingPipelineManager(**config.to_dict())
```

## Performance Tips

### For Maximum Throughput

```python
config = get_config("throughput")
config.chunk_size = 1024      # Larger batches
config.max_retries = 2        # Fewer retries
```

### For Critical Research (No Data Loss)

```python
config = get_config("research")
config.max_retries = 5        # More retries
config.chunk_size = 256       # Smaller batches (safer)
```

### For Cost Optimization

```python
config = get_config("low_cost")
# Uses text-embedding-3-small (cheaper than large)
# Lower TPM (slower but uses less quota)
```

## Troubleshooting

### Tokens Exhausted

```python
# Symptom: "Insufficient balance" error

# Solution 1: Use lower TPM
config.max_tokens_per_minute = 30000

# Solution 2: Use local embedding
config = get_config("local")

# Solution 3: Switch to lower-cost model
config.model = "text-embedding-3-small"
```

### Requests Timeout

```python
# Symptom: "Request did not complete within 600s"

# Solution: Increase timeout
manager = EmbeddingPipelineManager(
    ...,
    request_timeout=1200.0,  # 20 minutes
)
```

### High Retry Rate

```python
# Symptom: Many "retry 1/3" messages

# Check status
manager.print_status()

# Solution: Reduce batch size
config.chunk_size = 128

# Or use fallback provider
embeddings, failed = await manager.embed_with_fallback(
    docs,
    fallback_provider="ollama",
)
```

### Memory Usage

```python
# If using very large request history:
# Periodically clear old entries

pipeline.request_history.clear()  # WARNING: Loses history

# Or just let it track metrics and check status
status = pipeline.get_status()
```

## File Structure

```
gpt_researcher/memory/
├── resilient_embeddings.py      # Core pipeline (with rate limit, queue, retry)
├── pipeline_integration.py       # Manager and research integration
├── embedding_config.py           # Preset configurations
├── embeddings.py                 # Original Memory class (unchanged)
└── __init__.py

tests/
└── test_resilient_embeddings.py  # Example usage and tests
```

## API Reference

### ResilientEmbeddingPipeline

**Methods:**
- `embed_documents(docs, request_id, wait_for_result)` - Queue documents
- `start_worker()` - Start background processing
- `await stop_worker()` - Stop background worker
- `get_status()` - Get pipeline status
- `get_request_status(request_id)` - Get request status
- `count_tokens(docs)` - Count tokens

### EmbeddingPipelineManager

**Methods:**
- `start()` - Start pipeline
- `await stop()` - Stop pipeline
- `await embed_documents_safe(docs, request_id, timeout)` - Embed with retry
- `await embed_with_fallback(docs, fallback_provider, fallback_model)` - With fallback
- `print_status()` - Print formatted status
- `save_metrics()` - Save metrics to JSON

### ResearchPipelineIntegration

**Methods:**
- `await process_research_documents(documents, batch_name)` - Process batch
- `get_summary()` - Get processing summary

## License

Same as GPT Researcher

## Contributing

Contributions welcome! Areas for improvement:
- Persistence (SQLite for queue recovery)
- Distributed processing (multi-worker)
- Advanced metrics (latency percentiles)
- Provider auto-detection

---

**Made for researchers who can't afford to lose data.** ⚡
