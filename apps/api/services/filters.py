from collections.abc import Mapping
from typing import Any

from django.http import QueryDict

from apps.client.services.client_helpers import get_filtered_events
from apps.common.models import Event

FILTER_NAMES = (
    "group",
    "teacher",
    "place",
    "subject",
    "kind",
    "time_slot",
)


def filters_from_query(query: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "date": _get_first(query, "date") or "today",
        "left_date": _get_first(query, "left_date") or "",
        "right_date": _get_first(query, "right_date") or "",
        **{name: _get_list(query, name) for name in FILTER_NAMES},
    }


def get_events_for_query(query: Mapping[str, Any]):
    filters = filters_from_query(query)
    events = get_filtered_events(filters)
    return optimize_event_queryset(events)


def optimize_event_queryset(events):
    return events.select_related(
        "abstract_event",
        "abstract_event__abstract_day",
        "abstract_event__schedule",
        "abstract_event__schedule__metadata",
        "abstract_event__schedule__schedule_template",
        "abstract_event__schedule__schedule_template__metadata",
        "abstract_event__schedule__schedule_template__department",
        "subject_override",
        "kind_override",
        "time_slot_override",
    ).prefetch_related(
        "participants_override",
        "participants_override__department",
        "places_override",
    )


def _get_first(query: Mapping[str, Any], name: str) -> str:
    if isinstance(query, QueryDict):
        return query.get(name, "")
    value = query.get(name, "")
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)


def _get_list(query: Mapping[str, Any], name: str) -> list[str]:
    if isinstance(query, QueryDict):
        values = query.getlist(name) or query.getlist(f"{name}[]")
        return [value for value in values if value]
    value = query.get(name, [])
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)] if value else []
