import logging
from http import HTTPStatus

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest
from dmr import APIError
from dmr.errors import format_error

logger = logging.getLogger(__name__)

EXPORT_ANONYMOUS_RATE_LIMIT = settings.API_EXPORT_ANONYMOUS_RATE_LIMIT
EXPORT_ANONYMOUS_RATE_WINDOW_SECONDS = settings.API_EXPORT_ANONYMOUS_RATE_WINDOW_SECONDS
TOKEN_RATE_LIMIT = settings.API_TOKEN_RATE_LIMIT
TOKEN_RATE_WINDOW_SECONDS = settings.API_TOKEN_RATE_WINDOW_SECONDS


def enforce_anonymous_export_rate_limit(request: HttpRequest) -> None:
    _enforce_rate_limit(
        request,
        key_prefix="api:export:anonymous",
        max_requests=EXPORT_ANONYMOUS_RATE_LIMIT,
        window_seconds=EXPORT_ANONYMOUS_RATE_WINDOW_SECONDS,
        message="Too many export requests. Try again later.",
    )


def enforce_token_rate_limit(request: HttpRequest) -> None:
    _enforce_rate_limit(
        request,
        key_prefix="api:token",
        max_requests=TOKEN_RATE_LIMIT,
        window_seconds=TOKEN_RATE_WINDOW_SECONDS,
        message="Too many token requests. Try again later.",
    )


def _enforce_rate_limit(
    request: HttpRequest,
    *,
    key_prefix: str,
    max_requests: int,
    window_seconds: int,
    message: str,
) -> None:
    remote_addr = request.META.get("REMOTE_ADDR", "unknown")
    key = f"{key_prefix}:{remote_addr}"
    try:
        added = cache.add(key, 1, window_seconds)
        count = 1 if added else cache.incr(key)
    except Exception as exc:
        logger.warning("API rate limit cache failed: %s", exc)
        return

    if count > max_requests:
        raise APIError(
            format_error(message),
            status_code=HTTPStatus.TOO_MANY_REQUESTS,
        )
