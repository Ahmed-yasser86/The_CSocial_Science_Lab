from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from Retrival_Pipline.Graph.Chains.ChainUtil import build_chat_model

class RouteQuery(BaseModel):
    """Represents the routing decision for a user query."""

    datasource: Literal["vectorstore", "websearch"] = Field(
        ...,
        description="Select whether the query should be answered using the vector store or web search.",
    )


router_llm = build_chat_model()

structured_router = router_llm.with_structured_output(RouteQuery)

router_system_prompt = """
You are an expert at routing a user question to either a vectorstore or web search.

The vectorstore contains documents about:
- AI agents
- Prompt engineering
- Adversarial attacks

Use the vectorstore only for these topics.
For all other questions, use web search.
"""

router_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", router_system_prompt),
        ("human", "{question}"),
    ]
)

question_router = router_prompt | structured_router