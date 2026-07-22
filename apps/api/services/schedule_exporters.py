import csv
import io
from collections.abc import Sequence
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import msgspec
from django.conf import settings
from icalendar import Calendar
from icalendar import Event as CalendarEvent

from apps.api.schemas import (
    ApiScheduleEvent,
    ApiScheduleException,
    ApiScheduleExportResponse,
)
from apps.api.services.exporters import ExportedFile, _export_filename, _join_names


def export_schedule(
    schedule_events: list[ApiScheduleEvent],
    format_name: str,
    filters: dict[str, Any],
) -> ExportedFile:
    normalized_format = format_name.lower()
    if normalized_format == "json":
        return _export_json(schedule_events, filters)
    if normalized_format == "csv":
        return _export_csv(schedule_events, filters)
    if normalized_format in {"ics", "ical", "icalendar"}:
        return _export_ics(schedule_events, filters)
    raise ValueError(f"Unsupported export format: {format_name}")


def _export_json(schedule_events: list[ApiScheduleEvent], filters: dict[str, Any]) -> ExportedFile:
    payload = ApiScheduleExportResponse(
        mode="schedule",
        filters=filters,
        schedule_event_count=len(schedule_events),
        exception_count=sum(len(item.exceptions) for item in schedule_events),
        schedule_events=schedule_events,
    )
    return ExportedFile(
        body=msgspec.json.encode(payload),
        content_type="application/json; charset=utf-8",
        filename=_export_filename(filters, "json"),
    )


def _export_csv(schedule_events: list[ApiScheduleEvent], filters: dict[str, Any]) -> ExportedFile:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "record_type",
            "schedule_event_id",
            "event_id",
            "recurrence_kind",
            "abstract_day_name",
            "abstract_day_number",
            "first_date",
            "last_date",
            "interval_days",
            "occurrence_count",
            "original_date",
            "date",
            "start_time",
            "end_time",
            "subject",
            "kind",
            "groups",
            "teachers",
            "places",
            "is_canceled",
            "is_moved",
            "is_modified",
        ]
    )
    for schedule_event in schedule_events:
        writer.writerow(_schedule_event_csv_row(schedule_event))
        for exception in schedule_event.exceptions:
            writer.writerow(_exception_csv_row(schedule_event, exception))
    return ExportedFile(
        body=output.getvalue().encode("utf-8-sig"),
        content_type="text/csv; charset=utf-8",
        filename=_export_filename(filters, "csv"),
    )


def _schedule_event_csv_row(schedule_event: ApiScheduleEvent) -> list[object]:
    recurrence = schedule_event.recurrence
    return [
        "schedule_event",
        schedule_event.id,
        "",
        recurrence.kind,
        schedule_event.abstract_day.name,
        schedule_event.abstract_day.day_number,
        recurrence.first_date.isoformat(),
        recurrence.last_date.isoformat(),
        recurrence.interval_days or "",
        recurrence.occurrence_count,
        "",
        "",
        _start_time(schedule_event),
        _end_time(schedule_event),
        schedule_event.subject.name if schedule_event.subject else "",
        schedule_event.kind.name if schedule_event.kind else "",
        _join_names(schedule_event.groups),
        _join_names(schedule_event.teachers),
        "; ".join(place.display_name for place in schedule_event.places),
        "0",
        "0",
        "0",
    ]


def _exception_csv_row(
    schedule_event: ApiScheduleEvent, exception: ApiScheduleException
) -> list[object]:
    return [
        "exception",
        schedule_event.id,
        exception.event_id,
        "",
        schedule_event.abstract_day.name,
        schedule_event.abstract_day.day_number,
        "",
        "",
        "",
        "",
        exception.original_date.isoformat(),
        exception.date.isoformat(),
        exception.time_slot.start_time.isoformat(timespec="minutes")
        if exception.time_slot and exception.time_slot.start_time
        else "",
        exception.time_slot.end_time.isoformat(timespec="minutes")
        if exception.time_slot and exception.time_slot.end_time
        else "",
        exception.subject.name if exception.subject else "",
        exception.kind.name if exception.kind else "",
        _join_names(exception.groups),
        _join_names(exception.teachers),
        "; ".join(place.display_name for place in exception.places),
        "1" if exception.is_canceled else "0",
        "1" if exception.is_moved else "0",
        "1" if exception.is_modified else "0",
    ]


def _export_ics(schedule_events: list[ApiScheduleEvent], filters: dict[str, Any]) -> ExportedFile:
    calendar = Calendar()
    calendar.add("prodid", "-//VSTU Schedule//API//RU")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "PUBLISH")

    for schedule_event in schedule_events:
        calendar.add_component(_base_calendar_event(schedule_event))
        for exception in schedule_event.exceptions:
            calendar.add_component(_exception_calendar_event(schedule_event, exception))

    return ExportedFile(
        body=calendar.to_ical(),
        content_type="text/calendar; charset=utf-8",
        filename=_export_filename(filters, "ics"),
    )


def _base_calendar_event(schedule_event: ApiScheduleEvent) -> CalendarEvent:
    event = CalendarEvent()
    _add_common_properties(event, schedule_event)
    event.add("dtstart", _schedule_datetime(schedule_event, schedule_event.recurrence.first_date))
    event.add(
        "dtend",
        _schedule_datetime(schedule_event, schedule_event.recurrence.first_date, end=True),
    )
    if schedule_event.recurrence.kind == "recurring":
        event.add(
            "rrule",
            {
                "freq": "daily",
                "interval": schedule_event.recurrence.interval_days,
                "count": schedule_event.recurrence.occurrence_count,
            },
        )
    event.add("status", "CONFIRMED")
    return event


def _exception_calendar_event(
    schedule_event: ApiScheduleEvent, exception: ApiScheduleException
) -> CalendarEvent:
    event = CalendarEvent()
    event.add("uid", _schedule_uid(schedule_event))
    event.add("dtstamp", datetime.now(UTC))
    event.add("recurrence-id", _schedule_datetime(schedule_event, exception.original_date))
    if exception.is_canceled:
        event.add("status", "CANCELLED")
        return event

    event.add("dtstart", _exception_datetime(exception))
    event.add("dtend", _exception_datetime(exception, end=True))
    event.add("summary", exception.subject.name if exception.subject else "Schedule event")
    event.add("description", _description(exception.kind, exception.groups, exception.teachers))
    event.add("location", "; ".join(place.display_name for place in exception.places))
    event.add("status", "CONFIRMED")
    return event


def _add_common_properties(event: CalendarEvent, schedule_event: ApiScheduleEvent) -> None:
    event.add("uid", _schedule_uid(schedule_event))
    event.add("dtstamp", datetime.now(UTC))
    event.add(
        "summary", schedule_event.subject.name if schedule_event.subject else "Schedule event"
    )
    event.add(
        "description",
        _description(schedule_event.kind, schedule_event.groups, schedule_event.teachers),
    )
    event.add("location", "; ".join(place.display_name for place in schedule_event.places))


def _description(kind: object, groups: Sequence[object], teachers: Sequence[object]) -> str:
    parts = []
    kind_name = getattr(kind, "name", "")
    if kind_name:
        parts.append(kind_name)
    if groups:
        parts.append(f"Группы: {_join_names(groups)}")
    if teachers:
        parts.append(f"Преподаватели: {_join_names(teachers)}")
    return "\n".join(parts)


def _schedule_uid(schedule_event: ApiScheduleEvent) -> str:
    return f"schedule-event-{schedule_event.id}@vstu-schedule"


def _schedule_datetime(
    schedule_event: ApiScheduleEvent, date_value: date, *, end: bool = False
) -> datetime:
    slot = schedule_event.time_slot
    time_value = slot.end_time if end and slot else slot.start_time if slot else None
    return _localized_datetime(date_value, time_value, end=end)


def _exception_datetime(exception: ApiScheduleException, *, end: bool = False) -> datetime:
    slot = exception.time_slot
    time_value = slot.end_time if end and slot else slot.start_time if slot else None
    return _localized_datetime(exception.date, time_value, end=end)


def _localized_datetime(date_value: date, time_value: time | None, *, end: bool) -> datetime:
    if time_value is None:
        time_value = time(hour=23, minute=59) if end else time.min
    return datetime.combine(date_value, time_value, tzinfo=ZoneInfo(settings.TIME_ZONE))


def _start_time(schedule_event: ApiScheduleEvent) -> str:
    if schedule_event.time_slot and schedule_event.time_slot.start_time:
        return schedule_event.time_slot.start_time.isoformat(timespec="minutes")
    return ""


def _end_time(schedule_event: ApiScheduleEvent) -> str:
    if schedule_event.time_slot and schedule_event.time_slot.end_time:
        return schedule_event.time_slot.end_time.isoformat(timespec="minutes")
    return ""
