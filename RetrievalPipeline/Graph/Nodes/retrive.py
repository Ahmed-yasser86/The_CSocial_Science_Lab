from typing import Any, Dict
from dotenv import load_dotenv

from RetrievalPipeline.Graph.StateGraph import GraphState
from Ingestion_Pipline.config.settings import EmbeddingSettings
from Ingestion_Pipline.infra.embeddings import build_embeddings
from Ingestion_Pipline.RagRetrival import retive_query

load_dotenv()

embeddings = build_embeddings(EmbeddingSettings())

async def retrieve(state: GraphState) -> Dict[str, Any]:
    print("---RETRIEVE---")
    question = state["question"]

    documents =  await retive_query(
        embeddings,
        "MyAgenticRagApp",
        question
    )

    return {"documents": documents, "question": question}