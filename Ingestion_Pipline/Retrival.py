# from __future__ import annotations

# from dotenv import load_dotenv

# from config.settings import ChatModelSettings, DEFAULT_COLLECTION_NAME, EmbeddingSettings
# from infra.embeddings import build_embeddings
# from infra.vector_store import get_vector_db as _get_vector_db
# # from retrieval.agent import build_chat_model, build_retrieval_tool, run_llm as _run_llm
# # model = build_chat_model(ChatModelSettings())

# load_dotenv()

# COLLECTION_NAME = DEFAULT_COLLECTION_NAME

# embeddings = build_embeddings(EmbeddingSettings())


# async def get_vector_db(embedding, collection_name: str = COLLECTION_NAME):
#     return _get_vector_db(embedding, collection_name)





# # vector_db =  get_vector_db(embeddings)

# # retrieve_context = build_retrieval_tool(vector_db)


# # def run_llm(query: str):
# #     return _run_llm(query, model=model, retrieval_tool=retrieve_context)


# # if __name__ == "__main__":
# #     result = run_llm("What are Deep Agents?")

# #     print("\nAnswer:\n")
# #     print(result["answer"])

# #     print("\nRetrieved Documents:", len(result["context"]))
