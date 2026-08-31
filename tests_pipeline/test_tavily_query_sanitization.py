import importlib

import RetrievalPipeline.Graph.Nodes.web_search as web_search_module


def test_normalize_query_for_tavily_truncates_long_queries():
    long_query = "A" * 500 + " and more context"

    normalized = web_search_module.normalize_query_for_tavily(long_query)

    assert len(normalized) <= 400
    assert normalized.startswith("A")


def test_websearch_handles_non_list_documents(monkeypatch):
    class FakeTavily:
        def __init__(self, query=None, query_domains=None, **kwargs):
            pass

        def search(self, max_results=5):
            return {"results": [{"url": "http://example.com", "content": "ok", "title": "t"}]}

    monkeypatch.setattr(web_search_module, "TavilySearch", FakeTavily)

    result = web_search_module.websearch({"question": "short question", "documents": "not-a-list"})

    assert isinstance(result["documents"], list)
    assert any("ok" in d.page_content for d in result["documents"])
