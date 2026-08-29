"""
publisher_state.py's headers أحيانًا بتوصل كـ string بدل dict متوقع،
وده بيكسر generate_layout في اللحظة الأخيرة رغم إن التقرير كامل جاهز.
"""
import functools
from multi_agents.agents.publisher import PublisherAgent


_original_generate_layout = PublisherAgent.generate_layout


def _safe_generate_layout(self, research_state: dict):
    headers = research_state.get("headers")
    if isinstance(headers, str):
        # نحول الـ string لـ dict بأقل افتراض ممكن - بس title
        research_state = {**research_state, "headers": {"title": headers}}
    elif not isinstance(headers, dict):
        research_state = {**research_state, "headers": {"title": research_state.get("title", "")}}
    return _original_generate_layout(self, research_state)


PublisherAgent.generate_layout = _safe_generate_layout

print("✅ Patched PublisherAgent.generate_layout: يتعامل مع headers كـ string بأمان")