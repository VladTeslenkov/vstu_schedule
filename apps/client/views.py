from django.shortcuts import render
from django.template.defaulttags import register

from apps.client.services.client_helpers import make_table_data
from apps.common.models import Event
from apps.common.services.timetable.utilities.model_helpers import (
    get_all_groups,
    get_all_kinds,
    get_all_places,
    get_all_subjects,
    get_all_teachers,
    get_all_time_slots,
)
from apps.common.services.timetable.utilities.utilities import (
    is_events_follow_each_other,
    is_similar_events,
)


@register.filter
def get_list_item(list_ : list, i : int) -> int:
    """Used to get list element from templates
    """

    try:
        # i - 1 because template counter starts from 1
        return list_[i - 1]
    except IndexError:
        return None
    
@register.filter
def is_full_row_canceled(entry_events : list[Event], i : int) -> bool:
    """Used to make canceled full table row
    in situations where row consists of two Events
    """
    
    try:
        # i - 1 because template counter starts from 1

        # if next Event is the same
        # full cancel when both Events canceled
        if (
            is_events_follow_each_other(entry_events[i - 1], entry_events[i]) and 
            is_similar_events(entry_events[i - 1], entry_events[i])
        ):
            return entry_events[i - 1].is_event_canceled and entry_events[i].is_event_canceled
        
        # Otherwise when next Event different 
        return entry_events[i - 1].is_event_canceled
    except IndexError:
        # Out of range
        # Current event the last one
        return entry_events[i - 1].is_event_canceled
    
@register.filter
def is_time_slot_already_selected(time_slot : str, selected_time_slots : str|list[str]) -> bool:
    """Used to checks is given time slots considered as selected
    
    Created to prevent situations where
    '8:30' sets selected as '18:30'
    """
    
    if type(selected_time_slots) is list:
        return time_slot in selected_time_slots
    else:
        return time_slot == selected_time_slots

def index(request):
    context = {}

    if request.method == "POST":
        selected = {}

        if "date" in request.POST:
            selected["date"] = request.POST.get("date") or "today"
        else:
            selected["date"] = "today"

        if "left_date" in request.POST:
            selected["left_date"] = request.POST.get("left_date") or ""
        else:
            selected["left_date"] = ""
        
        if "right_date" in request.POST:
            selected["right_date"] = request.POST.get("right_date") or ""
        else:
            selected["right_date"] = ""

        selected["group"] = request.POST.getlist("group[]") or ""
        selected["teacher"] = request.POST.getlist("teacher[]") or ""
        selected["place"] = request.POST.getlist("place[]") or ""
        selected["subject"] = request.POST.getlist("subject[]") or ""
        selected["kind"] = request.POST.getlist("kind[]") or ""
        selected["time_slot"] = request.POST.getlist("time_slot[]") or ""

        context["selected"] = selected
        context["data"] = make_table_data(selected)

    context["groups"] = get_all_groups().values_list("name", flat=True)
    context["teachers"] = get_all_teachers().values_list("name", flat=True)
    context["places"] = [str(p) for p in get_all_places()]
    context["subjects"] = get_all_subjects().values_list("name", flat=True)
    context["kinds"] = get_all_kinds().values_list("name", flat=True)
    context["time_slots"] = [str(ts) for ts in get_all_time_slots()]

    context["addition_filters_visible"] = request.POST.get("addition_filters_visible") if "addition_filters_visible" in request.POST else "0"
    context["calendar_visibile"] = "1" if "calendar_visibility" in request.POST else "0"

    return render(request, "timetable/index.html", context=context)
