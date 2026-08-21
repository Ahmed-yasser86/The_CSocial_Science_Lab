from __future__ import annotations
from dotenv import load_dotenv
from Ingestion_Pipline.config.settings import ChatModelSettings, DEFAULT_COLLECTION_NAME, EmbeddingSettings
from Ingestion_Pipline.infra.embeddings import build_embeddings
from Ingestion_Pipline.infra.vector_store import get_vector_db as _get_vector_db
from Ingestion_Pipline.retrieval.retrive import retive_query
load_dotenv()

COLLECTION_NAME = DEFAULT_COLLECTION_NAME

embeddings = build_embeddings(EmbeddingSettings())

async def get_vector_db(embedding, collection_name: str = COLLECTION_NAME):
    return _get_vector_db(embedding, collection_name)


async def Retrive_Answere_From_Rag(embedding, collection_name,question):
    return await retive_query(embedding, collection_name,question)

