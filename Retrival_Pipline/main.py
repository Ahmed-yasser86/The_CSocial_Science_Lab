from typing import Any , Dict

from Graph.state import GraphState
from Ingestion_Pipline.config.settings import ChatModelSettings, DEFAULT_COLLECTION_NAME, EmbeddingSettings
from Ingestion_Pipline.infra.embeddings import build_embeddings

from Ingestion_Pipline.RagRetrival import  retive_query

embeddings = build_embeddings(EmbeddingSettings())


def retriveAnswerFromLLm(state:GraphState):
    print("retrive")
    question =state["question"]
    document = retive_query(embeddings,"MyAgenticRagApp",question)
    return {"question":question
            ,"documents":document}
