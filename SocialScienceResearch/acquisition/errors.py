"""Error taxonomy for the acquisition layer.

Classifying failures (instead of leaking raw library exceptions) makes
collection failures observable, comparable across runs, and retryable by
policy. The domain enum ``ErrorType`` is the vocabulary; these exception
classes carry it plus a ``retryable`` hint.
"""

from __future__ import annotations

from SocialScienceResearch.domain.enums import ErrorType


class AcquisitionError(Exception):
    """Base class for all acquisition errors."""

    error_type: ErrorType = ErrorType.UNKNOWN
    retryable: bool = False

    def __init__(self, message: str, *, entity_id: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.entity_id = entity_id


class NetworkError(AcquisitionError):
    error_type = ErrorType.NETWORK
    retryable = True


class RateLimitError(AcquisitionError):
    error_type = ErrorType.RATE_LIMIT
    retryable = True

    def __init__(
        self,
        message: str,
        *,
        entity_id: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, entity_id=entity_id)
        # Seconds the caller should wait before retrying (e.g. from a
        # Retry-After header). Consumed by the retry policy.
        self.retry_after = retry_after


class InvalidURLError(AcquisitionError):
    error_type = ErrorType.INVALID_URL


class NotFoundError(AcquisitionError):
    error_type = ErrorType.NOT_FOUND


class VideoUnavailableError(AcquisitionError):
    error_type = ErrorType.UNAVAILABLE


class CommentCollectionError(AcquisitionError):
    error_type = ErrorType.COMMENTS


class LibraryError(AcquisitionError):
    error_type = ErrorType.LIBRARY


class RecommendationUnsupportedError(AcquisitionError):
    error_type = ErrorType.RECOMMENDATION_UNSUPPORTED


class TranscriptUnsupportedError(AcquisitionError):
    error_type = ErrorType.TRANSCRIPT_UNSUPPORTED


class LiveEventSkipError(AcquisitionError):
    """Raised when a live/upcoming stream cannot be deep-extracted yet.

    Signals a *skip*, not a failure: an upcoming stream has no comments until
    it airs, so upstream code observes this as a skip (no error stats are
    polluted) while still persisting whatever metadata the flat entry carries.
    """

    error_type = ErrorType.UNAVAILABLE


class ValidationError(AcquisitionError):
    error_type = ErrorType.VALIDATION


_ERROR_CLASSES: dict[ErrorType, type[AcquisitionError]] = {
    ErrorType.NETWORK: NetworkError,
    ErrorType.RATE_LIMIT: RateLimitError,
    ErrorType.INVALID_URL: InvalidURLError,
    ErrorType.NOT_FOUND: NotFoundError,
    ErrorType.UNAVAILABLE: VideoUnavailableError,
    ErrorType.COMMENTS: CommentCollectionError,
    ErrorType.TRANSCRIPT_UNSUPPORTED: TranscriptUnsupportedError,
    ErrorType.LIBRARY: LibraryError,
    ErrorType.RECOMMENDATION_UNSUPPORTED: RecommendationUnsupportedError,
    ErrorType.VALIDATION: ValidationError,
}


def build_error(
    error_type: ErrorType, message: str, *, entity_id: str | None = None
) -> AcquisitionError:
    """Instantiate the appropriate acquisition error for an ``ErrorType``."""
    cls = _ERROR_CLASSES.get(error_type, AcquisitionError)
    return cls(message, entity_id=entity_id)


def classify_exception(exc: Exception) -> ErrorType:
    """Classify an arbitrary raised exception into our error vocabulary.

    Inspects both the type and the message because yt-dlp surfaces most
    failures as a generic ``DownloadError`` whose meaning is in its message.
    """
    if isinstance(exc, AcquisitionError):
        return exc.error_type

    text = f"{type(exc).__name__}: {exc}".lower()

    # Our own library's typed wrappers
    if isinstance(exc, (TimeoutError, ConnectionError, OSError, TimeoutError)):
        return ErrorType.NETWORK

    # URL-level failures
    if any(t in text for t in ("unsupported url", "invalid url", "is not a valid", "no video url", "unsupported")):
        return ErrorType.INVALID_URL

    # Availability failures
    if any(
        t in text
        for t in (
            "video unavailable",
            "this video is unavailable",
            "private video",
            "removed",
            "has been removed",
            "deleted",
            "account has been terminated",
            "copyright",
        )
    ):
        return ErrorType.UNAVAILABLE

    if any(t in text for t in ("not found", "doesn't exist", "404", "no longer exists")):
        return ErrorType.NOT_FOUND

    # Rate limiting
    if any(t in text for t in ("rate limit", "too many requests", "429", "quota exceeded")):
        return ErrorType.RATE_LIMIT

    # Generic network / transport
    if any(
        t in text
        for t in (
            "timed out",
            "timeout",
            "connection",
            "network",
            "could not",
            "http error 5",
            "http error 4",
            "temporarily unavailable",
            "cloudflare",
        )
    ):
        return ErrorType.NETWORK

    return ErrorType.LIBRARY
