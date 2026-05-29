from django.shortcuts import render
from django.template.defaulttags import register

from apps.client.services.client_helpers import make_table_data
from apps.common.models import Event
from apps.common.selectors import public_alerts
from apps.common.services.timetable.utilities import (
    is_events_follow_each_other,
    is_similar_events,
)
from apps.common.services.timetable.utilities.model_helpers import (
    get_all_groups,
    get_all_kinds,
    get_all_places,
    get_all_subjects,
    get_all_teachers,
    get_all_time_slots,
)


@register.filter
def get_list_item(list_: list, i: int) -> int | None:
    """Used to get list element from templates"""
    try:
        # i - 1 because template counter starts from 1
        return list_[i - 1]
    except IndexError:
        return None


@register.filter
def is_full_row_canceled(entry_events: list[Event], i: int) -> bool:
    """Used to make canceled full table row
    in situations where row consists of two Events
    """

    try:
        # i - 1 because template counter starts from 1

        # if next Event is the same
        # full cancel when both Events canceled
        if is_events_follow_each_other(entry_events[i - 1], entry_events[i]) and is_similar_events(
            entry_events[i - 1], entry_events[i]
        ):
            return entry_events[i - 1].is_event_canceled and entry_events[i].is_event_canceled

        # Otherwise when next Event different
        return entry_events[i - 1].is_event_canceled
    except IndexError:
        # Out of range
        # Current event the last one
        return entry_events[i - 1].is_event_canceled


@register.filter
def is_time_slot_already_selected(time_slot: str, selected_time_slots: str | list[str]) -> bool:
    """Used to checks is given time slots considered as selected

    Created to prevent situations where
    '8:30' sets selected as '18:30'
    """

    if type(selected_time_slots) is list:
        return time_slot in selected_time_slots
    else:
        return time_slot == selected_time_slots


@register.filter
def lesson_kind_class(kind: object) -> str:
    kind_name = str(kind).casefold()
    if "лаб" in kind_name:
        return "chip-kind--lab"
    if "пра" in kind_name or "пр." in kind_name:
        return "chip-kind--practice"
    if "лек" in kind_name:
        return "chip-kind--lecture"
    return ""


def _get_list_param(request, name: str) -> list[str]:
    values = request.GET.getlist(name)
    return values or request.GET.getlist(f"{name}[]")


def index(request):
    context = {}
    selected = {
        "date": "today",
        "left_date": "",
        "right_date": "",
        "group": [],
        "teacher": [],
        "place": [],
        "subject": [],
        "kind": [],
        "time_slot": [],
    }

    has_filters = bool(request.GET)
    if has_filters:
        selected["date"] = request.GET.get("date") or "today"
        selected["left_date"] = request.GET.get("left_date") or ""
        selected["right_date"] = request.GET.get("right_date") or ""
        selected["group"] = _get_list_param(request, "group")
        selected["teacher"] = _get_list_param(request, "teacher")
        selected["place"] = _get_list_param(request, "place")
        selected["subject"] = _get_list_param(request, "subject")
        selected["kind"] = _get_list_param(request, "kind")
        selected["time_slot"] = _get_list_param(request, "time_slot")
        context["data"] = make_table_data(selected)

    context["selected"] = selected
    context["groups"] = get_all_groups().values_list("name", flat=True)
    context["teachers"] = get_all_teachers().values_list("name", flat=True)
    context["places"] = [str(p) for p in get_all_places()]
    context["subjects"] = get_all_subjects().values_list("name", flat=True)
    context["kinds"] = get_all_kinds().values_list("name", flat=True)
    context["time_slots"] = [str(ts) for ts in get_all_time_slots()]

    context["addition_filters_visible"] = (
        request.GET.get("addition_filters_visible")
        if "addition_filters_visible" in request.GET
        else "0"
    )
    context["calendar_visible"] = "1" if "calendar_visibility" in request.GET else "0"
    context["has_filters"] = has_filters
    context["alerts"] = public_alerts()

    return render(request, "timetable/index.html", context=context)
