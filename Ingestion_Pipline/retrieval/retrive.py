from Ingestion_Pipline.infra.vector_store import get_vector_db as get_vector_db



async def retive_query(embedding, collection_name,question):
    vector_db = await get_vector_db(
    embedding=embedding,
    collection_name=collection_name
)
    retriever = vector_db.as_retriever()

    docs = retriever.invoke(question)

    return docs

