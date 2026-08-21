from __future__ import annotations

import logging

from google.api_core.exceptions import (
    DeadlineExceeded,
    InternalServerError,
    ResourceExhausted,
    ServiceUnavailable,
    TooManyRequests,
)
from langchain_google_genai._common import GoogleGenerativeAIError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GOOGLE_TRANSIENT_ERRORS = (
    TooManyRequests,
    ServiceUnavailable,
    InternalServerError,
    DeadlineExceeded,
)

GOOGLE_GENAI_TRANSIENT_ERRORS = (
    GoogleGenerativeAIError,
    TooManyRequests,
    ServiceUnavailable,
    InternalServerError,
    DeadlineExceeded,
)


def vector_dimension_retry():
    return retry(
        retry=retry_if_exception_type(GOOGLE_TRANSIENT_ERRORS),
        wait=wait_random_exponential(min=1, max=30),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.INFO),
        reraise=True,
    )


def document_add_retry():
    return retry(
        retry=retry_if_exception_type(GOOGLE_GENAI_TRANSIENT_ERRORS),
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(5),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


def url_extraction_retry():
    return retry(
        wait=wait_random_exponential(min=1, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
