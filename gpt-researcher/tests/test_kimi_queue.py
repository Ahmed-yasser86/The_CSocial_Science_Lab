#!/usr/bin/env python3
"""
Unit tests for Kimi Sequential Queue Worker.
Tests:
1. is_kimi_model detection for model names, providers, and environment variables.
2. Sequential request processing (concurrency = 1).
3. Retry loop behavior until success when temporary errors occur.
4. Transparent integration with create_chat_completion.
"""

import os
import unittest
import asyncio
from unittest.mock import AsyncMock, patch

from gpt_researcher.utils.kimi_queue import (
    is_kimi_model,
    KimiSequentialQueueManager,
    execute_via_kimi_queue,
)
from gpt_researcher.utils.llm import create_chat_completion


class TestKimiModelDetection(unittest.TestCase):
    def test_is_kimi_model_by_name(self):
        self.assertTrue(is_kimi_model(model="kimi-k1.5"))
        self.assertTrue(is_kimi_model(model="moonshot-v1-8k"))
        self.assertTrue(is_kimi_model(model="Kimi-latest"))
        self.assertFalse(is_kimi_model(model="gpt-4o"))

    def test_is_kimi_model_by_provider(self):
        self.assertTrue(is_kimi_model(provider="moonshot"))
        self.assertTrue(is_kimi_model(provider="kimi"))
        self.assertFalse(is_kimi_model(provider="openai"))

    def test_is_kimi_model_by_env(self):
        with patch.dict(os.environ, {"SMART_LLM_MODEL": "kimi-v1"}):
            self.assertTrue(is_kimi_model())


class TestKimiQueueExecution(unittest.IsolatedAsyncioTestCase):
    async def test_sequential_execution(self):
        """Verify that requests are processed sequentially (one after another)."""
        execution_order = []

        async def dummy_request(req_id, duration):
            execution_order.append(f"start_{req_id}")
            await asyncio.sleep(duration)
            execution_order.append(f"end_{req_id}")
            return f"result_{req_id}"

        # Submit 3 requests concurrently
        t1 = asyncio.create_task(execute_via_kimi_queue(dummy_request, 1, 0.05))
        t2 = asyncio.create_task(execute_via_kimi_queue(dummy_request, 2, 0.02))
        t3 = asyncio.create_task(execute_via_kimi_queue(dummy_request, 3, 0.01))

        results = await asyncio.gather(t1, t2, t3)

        self.assertEqual(results, ["result_1", "result_2", "result_3"])
        # Sequential verification: start_1 -> end_1 -> start_2 -> end_2 -> start_3 -> end_3
        expected_order = ["start_1", "end_1", "start_2", "end_2", "start_3", "end_3"]
        self.assertEqual(execution_order, expected_order)

    async def test_retry_on_failure(self):
        """Verify that a failing request is retried until it succeeds."""
        attempts = 0

        async def failing_request():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise RuntimeError(f"Simulated rate limit error on attempt {attempts}")
            return "success_after_retry"

        result = await execute_via_kimi_queue(failing_request)
        self.assertEqual(result, "success_after_retry")
        self.assertEqual(attempts, 3)

    async def test_create_chat_completion_kimi_routing(self):
        """Verify create_chat_completion automatically routes Kimi model calls via queue."""
        with patch("gpt_researcher.utils.llm._raw_create_chat_completion", new_callable=AsyncMock) as mock_raw:
            mock_raw.return_value = "Kimi response content"

            response = await create_chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="kimi-k1.5",
                llm_provider="moonshot"
            )

            self.assertEqual(response, "Kimi response content")
            mock_raw.assert_called_once()


if __name__ == "__main__":
    unittest.main()
