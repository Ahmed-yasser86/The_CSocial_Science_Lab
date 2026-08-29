"""
call_model في multi_agents/agents/utils/llms.py بتبلع أي Exception
وترجع None بصمت (مفيش raise بعد الـ except). ده سبب كل أخطاء
'NoneType has no attribute get' اللي بتحصل في reviewer/reviser بعدها.
"""
import functools
from multi_agents.agents.utils import llms as multi_agents_llms


_original_call_model = multi_agents_llms.call_model


@functools.wraps(_original_call_model)
async def _loud_call_model(prompt: list, model: str, response_format: str | None = None):
    result = await _original_call_model(prompt, model, response_format)
    if result is None:
        raise RuntimeError(
            "call_model رجّعت None - فشل الاستدعاء حتى بعد كل الـ retries. "
            "شوف اللوج فوق مباشرة لرسالة الخطأ الأصلية."
        )
    return result


multi_agents_llms.call_model = _loud_call_model

print("✅ Patched call_model: الفشل هيبان بوضوح بدل ما يترجع None بصمت")