from collections.abc import Callable
from typing import Any

from django.http import HttpRequest, HttpResponse
from dmr.plugins.msgspec import MsgspecSerializer
from dmr.routing import build_404_handler, build_500_handler

from apps.client.views import page_not_found, server_error

_api_404_handler = build_404_handler("api/", serializer=MsgspecSerializer)
_api_500_handler = build_500_handler("api/", serializer=MsgspecSerializer)


def handler404(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    return _route_error_handler(request, _api_404_handler, page_not_found, exception)


def handler500(request: HttpRequest) -> HttpResponse:
    return _route_error_handler(request, _api_500_handler, server_error)


def _route_error_handler(
    request: HttpRequest,
    api_handler: Callable[..., HttpResponse],
    client_handler: Callable[..., HttpResponse],
    *args: Any,
) -> HttpResponse:
    if request.path_info.startswith("/api/"):
        return api_handler(request, *args)
    return client_handler(request, *args)
