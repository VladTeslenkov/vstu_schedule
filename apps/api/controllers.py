import base64
from http import HTTPStatus

from django.http import HttpResponse
from dmr import APIError, Body, Controller, ResponseSpec, modify, validate
from dmr.errors import format_error
from dmr.plugins.msgspec import MsgspecSerializer
from dmr.renderers import FileRenderer, JsonRenderer

from apps.api.models import ApiClient
from apps.api.schemas import (
    ApiReference,
    ApiTokenRequest,
    ApiTokenResponse,
)
from apps.api.services.auth import (
    ApiClientTokenSyncAuth,
    StaffSessionSyncAuth,
    invalid_credentials_error,
    is_unlimited_request,
    issue_access_token,
)
from apps.api.services.exporters import export_events
from apps.api.services.filters import filters_from_query, get_events_for_query
from apps.api.services.rate_limits import (
    enforce_anonymous_export_rate_limit,
    enforce_token_rate_limit,
)
from apps.api.services.serialization import (
    serialize_events,
    serialize_participants,
    serialize_places,
    serialize_reference,
    serialize_subjects,
)
from apps.client.services.client_helpers import has_more_events_than
from apps.common.constants import CLIENT_MAX_FILTERED_EVENTS
from apps.common.services.timetable.utilities.model_helpers import (
    get_all_groups,
    get_all_places,
    get_all_subjects,
    get_all_teachers,
)


class ApiController(Controller[MsgspecSerializer]):
    serializer = MsgspecSerializer


class TokenController(ApiController):
    """Issue short-lived access tokens for API clients."""

    @modify(status_code=HTTPStatus.OK)
    def post(self, parsed_body: Body[ApiTokenRequest]) -> ApiTokenResponse:
        """Create an access-only JWT from client credentials."""
        enforce_token_rate_limit(self.request)
        try:
            client = ApiClient.objects.get(client_id=parsed_body.client_id)
        except ApiClient.DoesNotExist as exc:
            raise invalid_credentials_error() from exc

        if (
            not client.is_active
            or client.revoked_at is not None
            or not client.verify_secret(parsed_body.client_secret)
        ):
            raise invalid_credentials_error()

        token, expires_in = issue_access_token(client)
        client.mark_used()
        return ApiTokenResponse(
            access_token=token,
            token_type="Bearer",
            expires_in=expires_in,
            scope=client.allowed_scopes,
        )


class ReferenceController(ApiController):
    """Return all public timetable reference data."""

    def get(self) -> ApiReference:
        """Return groups, teachers, disciplines, and places."""
        return serialize_reference()


class ReferenceGroupsController(ApiController):
    def get(self) -> list:
        return serialize_participants(get_all_groups().select_related("department"))


class ReferenceTeachersController(ApiController):
    def get(self) -> list:
        return serialize_participants(get_all_teachers().select_related("department"))


class ReferenceDisciplinesController(ApiController):
    def get(self) -> list:
        return serialize_subjects(get_all_subjects().order_by("name"))


class ReferencePlacesController(ApiController):
    def get(self) -> list:
        return serialize_places(get_all_places().order_by("building", "room"))


class ExportController(ApiController):
    """Export the current timetable visualization request."""

    @validate(
        ResponseSpec(
            bytes,
            status_code=HTTPStatus.OK,
        ),
        renderers=[
            JsonRenderer(),
            FileRenderer("text/csv"),
            FileRenderer("text/calendar"),
            FileRenderer("text/html"),
        ],
        validate_responses=False,
        validate_negotiation=False,
    )
    def get(self) -> HttpResponse:
        """Return selected timetable events as JSON, CSV, or iCalendar."""
        format_name = _requested_format(self.request)
        unlimited = is_unlimited_request(self.request)
        if not unlimited:
            enforce_anonymous_export_rate_limit(self.request)

        filters = filters_from_query(self.request.GET)
        events = get_events_for_query(self.request.GET)
        if not unlimited and has_more_events_than(events, CLIENT_MAX_FILTERED_EVENTS):
            raise APIError(
                format_error(f"Too many events found. Limit is {CLIENT_MAX_FILTERED_EVENTS}."),
                status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )

        serialized_events = serialize_events(list(events))
        try:
            exported = export_events(serialized_events, format_name, filters)
        except ValueError as exc:
            raise APIError(
                format_error(str(exc)),
                status_code=HTTPStatus.BAD_REQUEST,
            ) from exc

        response = HttpResponse(exported.body, content_type=exported.content_type)
        response["X-Export-Filename"] = base64.b64encode(exported.filename.encode("utf-8")).decode("ascii")
        print(exported.filename)
        return response


def _requested_format(request) -> str:
    explicit_format = request.GET.get("format", "").lower()
    if explicit_format:
        return explicit_format

    accepted = request.headers.get("Accept", "")
    if "text/calendar" in accepted:
        return "ics"
    if "text/csv" in accepted:
        return "csv"
    return "json"
