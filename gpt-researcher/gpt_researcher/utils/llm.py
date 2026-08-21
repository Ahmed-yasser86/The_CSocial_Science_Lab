"""LLM utilities for GPT Researcher.

This module provides utility functions for interacting with various
LLM providers through a unified interface.
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, ClassVar
import asyncio

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from gpt_researcher.config.config import Config

from gpt_researcher.llm_provider.generic.base import (
    NO_SUPPORT_TEMPERATURE_MODELS,
    SUPPORT_REASONING_EFFORT_MODELS,
    ReasoningEfforts,
)

from ..prompts import PromptFamily
from .costs import calculate_llm_cost
from .validators import Subtopics
from .kimi_queue import is_kimi_model, execute_via_kimi_queue


class GlobalLLMRequestScheduler:
    _instance: ClassVar["GlobalLLMRequestScheduler"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.max_concurrency = 1
        self.delay_seconds = 30.0
        self._lock = None
        self._lock_loop = None
        self._semaphore = None
        self._semaphore_loop = None
        self.last_request_time = 0.0
        self._initialized = True

    def _get_lock(self) -> asyncio.Lock:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if self._lock is None or self._lock_loop != loop:
            self._lock = asyncio.Lock()
            self._lock_loop = loop
        return self._lock

    def _get_semaphore(self) -> asyncio.Semaphore:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if self._semaphore is None or self._semaphore_loop != loop:
            self._semaphore = asyncio.Semaphore(self.max_concurrency)
            self._semaphore_loop = loop
        return self._semaphore

    def configure(self, max_concurrency: int = 1, delay_seconds: float = 30.0):
        self.max_concurrency = max_concurrency
        self.delay_seconds = delay_seconds
        self._semaphore = None
        self._semaphore_loop = None

    @asynccontextmanager
    async def schedule(self):
        sem = self._get_semaphore()
        await sem.acquire()
        try:
            if self.delay_seconds > 0:
                lock = self._get_lock()
                async with lock:
                    now = time.time()
                    elapsed = now - self.last_request_time
                    sleep_time = self.delay_seconds - elapsed
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)
                    self.last_request_time = time.time()
            yield
        finally:
            sem.release()


_global_llm_scheduler = GlobalLLMRequestScheduler()


def get_llm(llm_provider: str, **kwargs):
    """Get an LLM provider instance.

    Args:
        llm_provider: The name of the LLM provider (e.g., 'openai', 'anthropic').
        **kwargs: Additional keyword arguments passed to the provider.

    Returns:
        A GenericLLMProvider instance configured for the specified provider.
    """
    from gpt_researcher.llm_provider import GenericLLMProvider
    return GenericLLMProvider.from_provider(llm_provider, **kwargs)


async def _raw_create_chat_completion(
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = 0.4,
        max_tokens: int | None = 4000,
        llm_provider: str | None = None,
        stream: bool = False,
        websocket: Any | None = None,
        llm_kwargs: dict[str, Any] | None = None,
        cost_callback: callable = None,
        reasoning_effort: str | None = ReasoningEfforts.Medium.value,
        **kwargs
) -> str:
    # Remove internal queue tracking kwarg before passing to LLM provider
    kwargs.pop("_from_kimi_queue", None)

    # validate input
    if model is None:
        raise ValueError("Model cannot be None")
    # Sanity guard against absurd values (e.g., env var typos). The actual
    # per-model output limits are enforced by the upstream provider.
    if max_tokens is not None and max_tokens > 200_000:
        raise ValueError(
            f"max_tokens={max_tokens} exceeds the largest output limit of "
            "any currently available model (128k as of late 2025). "
            "Check your FAST_TOKEN_LIMIT / SMART_TOKEN_LIMIT / "
            "STRATEGIC_TOKEN_LIMIT env vars for typos."
        )

    # Get the provider from supported providers
    provider_kwargs = {'model': model}

    if llm_kwargs:
        provider_kwargs.update(llm_kwargs)

    if model in SUPPORT_REASONING_EFFORT_MODELS:
        provider_kwargs['reasoning_effort'] = reasoning_effort

    if model not in NO_SUPPORT_TEMPERATURE_MODELS:
        provider_kwargs['temperature'] = temperature
    else:
        provider_kwargs['temperature'] = None
    provider_kwargs['max_tokens'] = max_tokens

    if llm_provider == "openai":
        base_url = os.environ.get("OPENAI_BASE_URL", None)
        if base_url:
            provider_kwargs['openai_api_base'] = base_url

    response = ""
    cfg = Config()
    _global_llm_scheduler.configure(
        max_concurrency=cfg.llm_request_concurrency,
        delay_seconds=cfg.llm_request_delay_seconds,
    )
    max_attempts = 1 if (stream and websocket is not None) else cfg.llm_max_attempts
    retry_delay_seconds = max(cfg.llm_request_delay_seconds, 30.0)
    last_exception: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            async with _global_llm_scheduler.schedule():
                provider = get_llm(llm_provider, **provider_kwargs)
                try:
                    llm_request_timeout = int(os.environ.get("LLM_REQUEST_TIMEOUT", "600"))
                except Exception:
                    llm_request_timeout = 10000

                logging.getLogger(__name__).debug(
                    "LLM request attempt %s/%s starting (provider=%s, model=%s, timeout=%s)",
                    attempt, max_attempts, llm_provider, model, llm_request_timeout,
                )

                try:
                    response = await asyncio.wait_for(
                        provider.get_chat_response(messages, stream, websocket, **kwargs),
                        timeout=llm_request_timeout,
                    )
                except asyncio.TimeoutError as te:
                    last_exception = te
                    logging.getLogger(__name__).debug(
                        "LLM request timed out; retrying if available"
                    )
                    if attempt < max_attempts:
                        await asyncio.sleep(retry_delay_seconds)
                        continue
                    break
        except Exception as exc:
            last_exception = exc
            logging.getLogger(__name__).warning(
                f"LLM request failed (attempt {attempt}/{max_attempts}): {exc}"
            )
            if attempt < max_attempts:
                await asyncio.sleep(retry_delay_seconds)
                continue
            break

        logging.getLogger(__name__).debug(
            "LLM request attempt %s/%s completed; response length=%s",
            attempt, max_attempts, len(response) if isinstance(response, str) else type(response),
        )

        if not response:
            last_exception = RuntimeError("Empty response from LLM provider")
            logging.getLogger(__name__).warning(
                f"LLM returned empty response (attempt {attempt}/{max_attempts})"
            )
            if attempt < max_attempts:
                await asyncio.sleep(retry_delay_seconds)
                continue
            break

        if cost_callback:
            llm_costs = calculate_llm_cost(
                llm_provider=llm_provider,
                model=model,
                input_content=str(messages),
                output_content=response,
                response_metadata=provider.last_response_metadata,
                usage_metadata=provider.last_usage_metadata,
                request_options=provider_kwargs,
            )
            cost_callback(llm_costs)

        return response

    logging.error(f"Failed to get response from {llm_provider} API")
    raise RuntimeError(f"Failed to get response from {llm_provider} API") from last_exception


async def create_chat_completion(
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = 0.4,
        max_tokens: int | None = 4000,
        llm_provider: str | None = None,
        stream: bool = False,
        websocket: Any | None = None,
        llm_kwargs: dict[str, Any] | None = None,
        cost_callback: callable = None,
        reasoning_effort: str | None = ReasoningEfforts.Medium.value,
        **kwargs
) -> str:
    """Create a chat completion using the OpenAI API / LLM Providers.
    
    If the model or provider is a Kimi / Moonshot model, requests are automatically
    routed sequentially via KimiSequentialQueueManager with persistent retries.
    """
    if is_kimi_model(model, llm_provider) and not kwargs.get("_from_kimi_queue"):
        kwargs["_from_kimi_queue"] = True
        return await execute_via_kimi_queue(
            _raw_create_chat_completion,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            llm_provider=llm_provider,
            stream=stream,
            websocket=websocket,
            llm_kwargs=llm_kwargs,
            cost_callback=cost_callback,
            reasoning_effort=reasoning_effort,
            **kwargs,
        )

    return await _raw_create_chat_completion(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        llm_provider=llm_provider,
        stream=stream,
        websocket=websocket,
        llm_kwargs=llm_kwargs,
        cost_callback=cost_callback,
        reasoning_effort=reasoning_effort,
        **kwargs,
    )


async def construct_subtopics(
    task: str,
    data: str,
    config,
    subtopics: list = [],
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
) -> list:
    """
    Construct subtopics based on the given task and data.

    Args:
        task (str): The main task or topic.
        data (str): Additional data for context.
        config: Configuration settings.
        subtopics (list, optional): Existing subtopics. Defaults to [].
        prompt_family (PromptFamily): Family of prompts
        **kwargs: Additional keyword arguments.

    Returns:
        list: A list of constructed subtopics.
    """
    try:
        parser = PydanticOutputParser(pydantic_object=Subtopics)

        prompt = PromptTemplate(
            template=prompt_family.generate_subtopics_prompt(),
            input_variables=["task", "data", "subtopics", "max_subtopics"],
            partial_variables={
                "format_instructions": parser.get_format_instructions()},
        )

        provider_kwargs = {'model': config.smart_llm_model}

        if config.llm_kwargs:
            provider_kwargs.update(config.llm_kwargs)

        if config.smart_llm_model in SUPPORT_REASONING_EFFORT_MODELS:
            provider_kwargs['reasoning_effort'] = ReasoningEfforts.High.value
        else:
            provider_kwargs['temperature'] = config.temperature
        provider_kwargs['max_tokens'] = config.smart_token_limit

        provider = get_llm(config.smart_llm_provider, **provider_kwargs)

        model = provider.llm

        chain = prompt | model | parser

        output = await chain.ainvoke({
            "task": task,
            "data": data,
            "subtopics": subtopics,
            "max_subtopics": config.max_subtopics
        }, **kwargs)

        return output

    except Exception as e:
        logging.getLogger(__name__).error(
            "Exception in parsing subtopics: %s", e, exc_info=True
        )
        return subtopics
