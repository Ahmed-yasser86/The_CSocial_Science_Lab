from ingestion_service import EmbedDocumentsToVectoreDb
import asyncio


urls = [
    [
    "https://lilianweng.github.io/posts/2023-06-23-agent/",
    "https://lilianweng.github.io/posts/2023-03-15-prompt-engineering/",
    "https://lilianweng.github.io/posts/2023-10-25-adv-attack-llm/",
]
]


async def main():
    embedding_results = await EmbedDocumentsToVectoreDb(
        urls,
        "MyAgenticRagApp",
    )

    print(embedding_results)


if __name__ == "__main__":
    asyncio.run(main())