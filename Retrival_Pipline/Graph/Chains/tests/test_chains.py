# import sys
# print(sys.path)
# from pprint import pprint
# from dotenv import load_dotenv
# from Ingestion_Pipline.RagRetrival import retive_query
# load_dotenv()
# from typing import cast
# from Ingestion_Pipline.config.settings import ChatModelSettings, DEFAULT_COLLECTION_NAME, EmbeddingSettings
# from Ingestion_Pipline.infra.embeddings import build_embeddings
# from Generate import generate_chain  
# from Ingestion_Pipline.RagRetrival import  retive_query
# from hallucination_grader import hallucination_grader
# from Retrival_Grader import GradeDocuments , retrival_grader
# from router import question_router

# embeddings = build_embeddings(EmbeddingSettings())

# import pytest

# @pytest.mark.asyncio
# async def test_retrival_grader_answer_yes():
#     question = "agent memory"

#     docs = await retive_query(
#         embeddings,
#         "MyAgenticRagApp",
#         question
#     )

#     doc_txt = docs[1].page_content


#     res = cast(
#     GradeDocuments,
#     retrival_grader.invoke(
#         {
#             "question": question,
#             "document": doc_txt
#         }
#     )
# )

    
#     assert res.binary_score == "yes"



# @pytest.mark.asyncio
# async def test_retrival_grader_answer_no():
#     question = "agent memory"

#     docs = await retive_query(
#         embeddings,
#         "MyAgenticRagApp",
#         question
#     )

#     doc_txt = docs[1].page_content


#     res = cast(
#     GradeDocuments,
#     retrival_grader.invoke(
#         {
#             "question": "how to make pizza",
#             "document": doc_txt
#         }
#     )
# )

    
#     assert res.binary_score == "no"



# # def test_retrival_grader_answer_no() -> None:
# #     question = "agent memory"
# #     docs = retriever.invoke(question)
# #     doc_txt = docs[1].page_content

# #     res: GradeDocuments = retrieval_grader.invoke(
# #         {"question": "how to make pizaa", "document": doc_txt}
# #     )

# #     assert res.binary_score == "no"

# @pytest.mark.asyncio
# async def test_generation_chain() -> None:
#     question = "agent memory"
#     docs = await retive_query(
#         embeddings,
#         "MyAgenticRagApp",
#         question
#     )

#     generation = generate_chain.invoke({"context": docs, "question": question})
#     pprint(generation)

# @pytest.mark.asyncio
# async def test_hallucination_grader_answer_yes() -> None:
#     question = "agent memory"
#     docs = await retive_query(
#         embeddings,
#         "MyAgenticRagApp",
#         question
#     )

#     generation = generate_chain.invoke({"context": docs, "question": question})

#     res: GradeHallucinations = hallucination_grader.invoke(
#         {"documents": docs, "generation": generation}
#     )
#     assert res.binary_score

# @pytest.mark.asyncio
# async def test_hallucination_grader_answer_NO() -> None:
#     question = "agent memory"
#     docs = await retive_query(
#         embeddings,
#         "MyAgenticRagApp",
#         question
#     )

#     res: GradeHallucinations = hallucination_grader.invoke(
#         {"documents": docs, "generation": "In order to make pizza we need to first start with the dough"}
#     )
#     assert not res.binary_score



# def test_router_to_vectorstore() -> None:
#     question = "agent memory"

#     res: RouteQuery = question_router.invoke({"question": question})
#     assert res.datasource == "vectorstore"


# def test_router_to_websearch() -> None:
#     question = "how to make pizza"

#     res: RouteQuery = question_router.invoke({"question": question})
#     assert res.datasource == "websearch"