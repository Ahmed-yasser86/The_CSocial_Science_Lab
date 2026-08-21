# from __future__ import annotations

# from typing import Any

# from langchain.agents import create_agent
# from langchain.chat_models import init_chat_model
# from langchain.messages import HumanMessage, ToolMessage
# from langchain.tools import tool
# from langchain_google_genai import GoogleGenerativeAIEmbeddings
# from langchain_qdrant import QdrantVectorStore

# from config.settings import ChatModelSettings, DEFAULT_RETRIEVAL_K, EmbeddingSettings
# from infra.embeddings import build_embeddings
# from infra.vector_store import get_vector_db

# SYSTEM_PROMPT = """
# You are a helpful AI assistant that answers questions about LangChain documentation.

# You have access to a retrieval tool.

# Always use the retrieval tool before answering.

# Base your answer only on the retrieved documentation whenever possible.

# Always cite the retrieved sources.

# If the answer cannot be found in the documentation, clearly say so.
# """


# def build_chat_model(settings: ChatModelSettings | None = None):
#     settings = settings or ChatModelSettings()
#     return init_chat_model(settings.model, model_provider=settings.provider)


# def build_retrieval_tool(
#     vector_store: QdrantVectorStore,
#     k: int = DEFAULT_RETRIEVAL_K,
# ):
#     @tool(response_format="content_and_artifact")
#     def retrieve_context(query: str):
#         """
#         Retrieve relevant LangChain documentation for answering user questions.
#         """
#         retriever = vector_store.as_retriever(search_kwargs={"k": k})
#         retrieved_docs = retriever.invoke(query)

#         serialized_docs = "\n\n".join(
#             f"Source: {doc.metadata.get('source', 'Unknown')}\n\n"
#             f"Content:\n{doc.page_content}"
#             for doc in retrieved_docs
#         )

#         return serialized_docs, retrieved_docs

#     return retrieve_context


# def _extract_answer_text(content: Any) -> str:
#     if isinstance(content, str):
#         return content

#     if isinstance(content, list):
#         return "\n".join(
#             block.get("text", "")
#             for block in content
#             if isinstance(block, dict) and block.get("type") == "text"
#         )

#     return str(content)


# def _extract_context_docs(messages: list[Any]) -> list[Any]:
#     context_docs: list[Any] = []

#     for message in messages:
#         if isinstance(message, ToolMessage) and isinstance(message.artifact, list):
#             context_docs.extend(message.artifact)

#     return context_docs


# def run_llm(
#     query: str,
#     model=None,
#     retrieval_tool=None,
#     system_prompt: str = SYSTEM_PROMPT,
# ) -> dict[str, Any]:
#     model = model if model is not None else build_chat_model()
#     tools = [retrieval_tool] if retrieval_tool is not None else [_default_retrieval_tool()]

#     agent =   create_agent(model=model, tools=tools, system_prompt=system_prompt)

#     response = agent.invoke({"messages": [HumanMessage(content=query)]})

#     last_message = response["messages"][-1]
#     answer = _extract_answer_text(last_message.content)
#     context_docs = _extract_context_docs(response["messages"])

#     return {"answer": answer, "context": context_docs}


# _default_retrieval_tool_instance = None


# async def _default_retrieval_tool():
#     global _default_retrieval_tool_instance
#     if _default_retrieval_tool_instance is None:
#         embeddings = build_embeddings(EmbeddingSettings())
#         vector_db = await get_vector_db(embeddings)
#         _default_retrieval_tool_instance = build_retrieval_tool(vector_db)
#     return _default_retrieval_tool_instance
