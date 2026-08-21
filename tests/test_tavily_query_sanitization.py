import importlib

import Retrival_Pipline.Graph.Nodes.web_search as web_search_module


def test_normalize_query_for_tavily_truncates_long_queries():
    long_query = "A" * 500 + " and more context"

    normalized = web_search_module.normalize_query_for_tavily(long_query)

    assert len(normalized) <= 400
    assert normalized.startswith("A")


def test_websearch_handles_non_list_documents(monkeypatch):
    class DummyTool:
        def invoke(self, payload):
            return {"results": [{"content": "ok"}]}

    monkeypatch.setattr(web_search_module, "web_search_tool", DummyTool())

    result = web_search_module.websearch({"question": "short question", "documents": "not-a-list"})

    assert isinstance(result["documents"], list)
    assert result["documents"][0].page_content == "ok"
