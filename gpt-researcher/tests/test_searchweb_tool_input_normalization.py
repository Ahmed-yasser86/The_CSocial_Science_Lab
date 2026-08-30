"""
Regression tests for MCP tool-call argument normalization.

Root cause (traced from trace-01a04d26-...json): the SEARCH_WEB MCP tool was
invoked with ``{"raw_args": "..."}`` instead of the ``{"query": "..."}`` its
Pydantic schema requires. The remote server rejected the call and returned the
validation error *inside the tool response body*:

    1 validation error for SearchWebInput
    query
      Field required [type=missing, input_value={'raw_args': '...'}, input_type=dict]

That error text then leaked into the research context. The normalization that
fixes this existed only on ``MCPToolSelector.preprocess_tool_input`` and was
never applied on the ``conduct_research_with_tools`` execution path.

These tests fail before the fix (raw_args is passed through untouched) and pass
after ``preprocess_mcp_tool_input`` is applied on every invocation path.
"""
import asyncio
import unittest
from unittest import mock

from gpt_researcher.mcp.normalization import preprocess_mcp_tool_input


class TestPreprocessMcpToolInput(unittest.TestCase):
    def test_search_web_raw_args_is_mapped_to_query(self):
        out = preprocess_mcp_tool_input("SEARCH_WEB", {"raw_args": "latest news about X"})
        self.assertEqual(out, {"query": "latest news about X"})
        self.assertNotIn("raw_args", out)

    def test_search_web_existing_query_is_preserved(self):
        out = preprocess_mcp_tool_input("SEARCH_WEB", {"query": "keep me"})
        self.assertEqual(out, {"query": "keep me"})

    def test_search_web_missing_query_raises(self):
        with self.assertRaises(ValueError):
            preprocess_mcp_tool_input("SEARCH_WEB", {"unrelated": 1})

    def test_search_stories_category_alias_is_mapped(self):
        out = preprocess_mcp_tool_input("SEARCH_STORIES", {"category": "Political Conflict"})
        self.assertEqual(out["category"], "POLITICAL")

    def test_non_dict_input_is_returned_unchanged(self):
        self.assertEqual(preprocess_mcp_tool_input("SEARCH_WEB", "raw string"), "raw string")

    def test_unknown_tool_passes_through(self):
        payload = {"foo": "bar"}
        self.assertEqual(preprocess_mcp_tool_input("SOME_OTHER_TOOL", payload), payload)


class _FakeCfg:
    strategic_llm_provider = "openai"
    strategic_llm_model = "gpt-4o-mini"
    llm_kwargs = {}


class _FakeMessage:
    def __init__(self, tool_calls):
        self.tool_calls = tool_calls
        self.content = ""


class _FakeBoundTools:
    def __init__(self, message):
        self._message = message

    async def ainvoke(self, messages):
        return self._message


class _FakeLLM:
    def bind_tools(self, tools):
        return _FakeBoundTools(_fake_message)


class _FakeProvider:
    def __init__(self):
        self.llm = _FakeLLM()

    @classmethod
    def from_provider(cls, provider, **kwargs):
        return cls()


# Captured by the fake SEARCH_WEB tool.
_received_args = {}
# Message returned by the fake LLM, set per-test.
_fake_message = None


class _FakeSearchWebTool:
    name = "SEARCH_WEB"

    def __init__(self):
        _received_args.clear()

    async def ainvoke(self, args):
        _received_args.update(args)
        # shape understood by MCPResearchSkill._process_tool_result
        return [{"title": "result", "body": "ok", "href": "mcp://SEARCH_WEB/0"}]


class TestConductResearchNormalizesArgs(unittest.IsolatedAsyncioTestCase):
    async def test_raw_args_from_llm_is_normalized_before_tool_call(self):
        """End-to-end: conduct_research_with_tools must hand `query` to SEARCH_WEB."""
        from gpt_researcher.mcp.research import MCPResearchSkill

        global _fake_message
        _fake_message = _FakeMessage(
            [{"name": "SEARCH_WEB", "args": {"raw_args": "latest news about X"}, "id": "call_1"}]
        )

        tool = _FakeSearchWebTool()
        skill = MCPResearchSkill(cfg=_FakeCfg(), researcher=None)

        with mock.patch(
            "gpt_researcher.llm_provider.generic.base.GenericLLMProvider",
            _FakeProvider,
        ):
            results = await skill.conduct_research_with_tools("query", [tool])

        # The bug: args reached the tool as {"raw_args": ...} and the server
        # returned a validation error in the body.
        self.assertNotIn("raw_args", _received_args,
                         "SEARCH_WEB received raw_args instead of query")
        self.assertEqual(_received_args.get("query"), "latest news about X")
        self.assertTrue(results, "expected at least one formatted result")


if __name__ == "__main__":
    unittest.main()
