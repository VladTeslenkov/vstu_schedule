from django.http import QueryDict
from django.shortcuts import redirect, render
from django.template.defaulttags import register

from apps.client.services.client_helpers import (
    TooManyEventsFoundError,
    get_cached_filter_options,
    make_table_data,
)
from apps.common.models import Event
from apps.common.selectors import public_alerts
from apps.common.services.timetable.utilities import (
    is_events_follow_each_other,
    is_similar_events,
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


def _clean_get_params(params: QueryDict) -> QueryDict:
    cleaned = params.copy()
    for name in list(cleaned):
        values = [value for value in cleaned.getlist(name) if value != ""]
        if values:
            cleaned.setlist(name, values)
        else:
            del cleaned[name]

    if cleaned.get("addition_filters_visible") == "0":
        del cleaned["addition_filters_visible"]

    return cleaned


def index(request):
    if request.method == "GET":
        cleaned_get = _clean_get_params(request.GET)
        if cleaned_get.urlencode() != request.GET.urlencode():
            query = cleaned_get.urlencode()
            return redirect(f"{request.path}?{query}" if query else request.path)

    context: dict[str, object] = {"too_many_events_found": False}
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
        try:
            context["data"] = make_table_data(selected)
        except TooManyEventsFoundError as error:
            context["data"] = []
            context["too_many_events_found"] = True
            context["max_filtered_events"] = error.limit

    context["selected"] = selected
    context.update(get_cached_filter_options())

    context["addition_filters_visible"] = (
        request.GET.get("addition_filters_visible")
        if "addition_filters_visible" in request.GET
        else "0"
    )
    context["calendar_visible"] = "1" if "calendar_visibility" in request.GET else "0"
    context["has_filters"] = has_filters
    context["alerts"] = public_alerts()

    return render(request, "timetable/index.html", context=context)
