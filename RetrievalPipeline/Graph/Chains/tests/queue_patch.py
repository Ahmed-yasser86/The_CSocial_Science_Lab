# """
# يزود max_retries الافتراضي في create_chat_completion (كانت 10).
# مكمّل لـ queue_patch.py مش بديل عنه.
# """
# import functools
# from gpt_researcher.utils import llm as gpt_researcher_llm


# NEW_MAX_RETRIES = 60

# _original_create_chat_completion = gpt_researcher_llm.create_chat_completion


# @functools.wraps(_original_create_chat_completion)
# async def _retry_tuned_create_chat_completion(*args, **kwargs):
#     kwargs.setdefault("max_retries", NEW_MAX_RETRIES)
#     return await _original_create_chat_completion(*args, **kwargs)


# gpt_researcher_llm.create_chat_completion = _retry_tuned_create_chat_completion

# print(f"✅ Retry config applied: max_retries={NEW_MAX_RETRIES}")