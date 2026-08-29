from typing import Any

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, ToolMessage, SystemMessage
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from Ingestion_Pipline.config.settings import ChatModelSettings, DEFAULT_RETRIEVAL_K, EmbeddingSettings
from RetrievalPipeline.Graph.Chains.ChainUtil import build_chat_model


class GradeDocuments(BaseModel):
    """Binary score for relevance check on retrieved documents."""

    binary_score: str = Field(
        description="Documents are relevant to the question, 'yes' or 'no'"
    )


llm = build_chat_model()

llm_with_structured_output =llm.with_structured_output(GradeDocuments)




system = """
You are an expert RAG retrieval evaluator.

Your task is to determine whether a retrieved document is relevant to the user's question.

Evaluation rules:

1. Mark the document as "yes" if:
   - It directly answers the question.
   - It contains facts, explanations, examples, or context useful for answering.
   - It provides partial information that can contribute to the final answer.
   - It is semantically related even if it does not share exact keywords.

2. Mark the document as "no" if:
   - It discusses a different topic.
   - It only shares similar words but not meaning.
   - It lacks useful information for answering the question.
   - It is too vague or unrelated.

Do not judge writing quality.
Do not answer the user's question.
Only evaluate document relevance.

Output only:
- "yes"
- "no"
"""
grade_document = ChatPromptTemplate.from_messages(
    [
        ("system", system),
        (
            "human",
            "Retrieved document:\n\n{document}\n\nUser question:\n\n{question}"
        ),
    ]
)


retrival_grader = grade_document | llm_with_structured_output

