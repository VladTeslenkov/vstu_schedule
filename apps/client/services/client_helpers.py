from collections import defaultdict
from datetime import timedelta
from typing import cast

from django.db.models import QuerySet

from apps.common.models import AbstractEvent, Event
from apps.common.selectors import Selector
from apps.common.services.timetable.read.filters import (
    DateFilter,
    KindFilter,
    ParticipantFilter,
    PlaceFilter,
    ScheduleFilter,
    SubjectFilter,
    TimeSlotFilter,
)
from apps.common.services.timetable.utilities import (
    get_name_from_month_number,
    is_events_follow_each_other,
    is_similar_events,
)
from apps.common.services.timetable.write.factories import (
    calculate_semester_filling_parameters,
)

CalendarData = tuple[list[str], list[list[int | str]]]
EventGroup = list[Event]
RowSpans = list[int]
TableDataRow = tuple[EventGroup, RowSpans, CalendarData]
MAX_FILTERED_EVENTS = 250


class TooManyEventsFoundError(Exception):
    def __init__(self, limit: int) -> None:
        self.limit = limit
        super().__init__(f"Found more than {limit} events.")


def make_table_data(filters: dict, max_events: int = MAX_FILTERED_EVENTS) -> list[TableDataRow]:
    """Used to get filtered and formated data ready to visualisation"""
    events = get_filtered_events(filters)

    if has_more_events_than(events, max_events):
        raise TooManyEventsFoundError(max_events)

    entries = format_events(events)
    row_spans = make_row_spans(entries)
    calendar = make_calendar(entries)

    return list(zip(entries, row_spans, calendar, strict=True))


def get_filtered_events(filters: dict) -> QuerySet[Event]:
    reader = Selector()
    # Currently working ONLY with ACTIVE Schedules
    # TODO: selector for ARCHIVE and other Schdules
    reader.add_filter(ScheduleFilter.is_active())

    if filters["date"] == "today":
        reader.add_filter(DateFilter.today())
    elif filters["date"] == "tomorrow":
        reader.add_filter(DateFilter.tomorrow())
    elif filters["date"] == "this_week":
        reader.add_filter(DateFilter.this_week())
    elif filters["date"] == "next_week":
        reader.add_filter(DateFilter.next_week())
    elif filters["date"] == "single_date" and filters["left_date"] != "":
        reader.add_filter(DateFilter.from_singe_date(filters["left_date"]))
    elif (
        filters["date"] == "range_date"
        and filters["left_date"] != ""
        and filters["right_date"] != ""
    ):
        reader.add_filter(DateFilter.from_date(filters["left_date"], filters["right_date"]))

    if filters["group"]:
        reader.add_filter(ParticipantFilter.by_name(filters["group"]))

    if filters["place"]:
        reader.add_filter(PlaceFilter.by_building_and_room_event_relative(filters["place"]))

    if filters["subject"]:
        reader.add_filter(SubjectFilter.by_name(filters["subject"]))

    if filters["kind"]:
        reader.add_filter(KindFilter.by_name(filters["kind"]))

    if filters["time_slot"]:
        reader.add_filter(TimeSlotFilter.from_display_name_event_relative(filters["time_slot"]))

    reader.find_models(Event)

    if filters["teacher"]:
        return (
            reader.get_found_models()
            .filter(**ParticipantFilter.by_name(filters["teacher"]))
            .distinct()
        )

    return reader.get_found_models()


def has_more_events_than(events: QuerySet[Event], limit: int) -> bool:
    if limit < 0:
        raise ValueError("limit must not be negative")

    limited_event_ids = events.order_by().values_list("pk", flat=True).distinct()[: limit + 1]
    return len(limited_event_ids) > limit


def format_events(events: QuerySet) -> list[EventGroup]:
    """Format events by grouping them and ordering by date"""

    events = events.order_by("time_slot_override__start_time", "date")

    # grouping found events by date
    grouped_events = defaultdict(list)

    for e in events:
        grouped_events[e.date].append(e)

    # ordering groups of events by date
    return [event_group for _, event_group in sorted(grouped_events.items())]


def make_row_spans(entries: list[EventGroup]) -> list[RowSpans]:
    """Returns a list of table row spans"""

    row_spans = []

    for entry in entries:
        row_spans.append([])
        prev_event_expanded = False

        for i in range(0, len(entry)):
            # if previous row expanded
            # need to collaspe current
            if prev_event_expanded:
                row_spans[len(row_spans) - 1].append(0)
                prev_event_expanded = False
                continue

            # skip last row
            if i + 1 >= len(entry):
                row_spans[len(row_spans) - 1].append(1)
                continue

            if is_events_follow_each_other(entry[i], entry[i + 1]) and is_similar_events(
                entry[i], entry[i + 1]
            ):
                row_spans[len(row_spans) - 1].append(2)
                prev_event_expanded = True
            else:
                row_spans[len(row_spans) - 1].append(1)

    return row_spans


def make_calendar(entries: list[EventGroup]) -> list[CalendarData]:
    """Makes and returns calendar for given entries

    Calendar format:
    [
        [
            ['Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь', 'Январь'],
            [
                [1, 13, 10, 8, 5],
                [15, 27, 24, 22, 19],
                [29, '', '', '', '']
            ]
        ]
    ]
    """

    calendar = []

    for entry in entries:
        months = []
        month_days = []
        dates = []
        abstract_event = cast(AbstractEvent, entry[0].abstract_event)
        _, end_date, date, repetition_period = calculate_semester_filling_parameters(abstract_event)

        while date < end_date:
            if date.month not in months:
                months.append(date.month)

                if dates:
                    month_days.append(dates)
                    dates = []

            dates.append(date.day)

            date += timedelta(days=repetition_period)

        if dates:
            month_days.append(dates)
            dates = []

        month_names = cast(list[str], get_name_from_month_number(months))
        calendar.append((month_names, format_days(month_days)))

        # calendar can be builded from first event each day
        continue

    return calendar


def format_days(days: list[list[int]]) -> list[list[int | str]]:
    """Transforms days order from column into row oriented"""

    max_days_count = 0
    formated_days = []

    for d in days:
        if len(d) > max_days_count:
            max_days_count = len(d)

    for i in range(max_days_count):
        row = []
        for d in days:
            if i >= len(d):
                row.append("")
                continue
            row.append(d[i])

        formated_days.append(row)

    return formated_days
