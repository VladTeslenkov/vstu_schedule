import csv
import io
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import msgspec
from icalendar import Calendar
from icalendar import Event as CalendarEvent

from apps.api.schemas import ApiEvent, ApiExportResponse


@dataclass(frozen=True)
class ExportedFile:
    body: bytes
    content_type: str
    filename: str


def export_events(
    events: list[ApiEvent],
    format_name: str,
    filters: dict[str, Any] | None = None,
) -> ExportedFile:
    normalized_format = format_name.lower()
    if normalized_format == "json":
        return export_json(events, filters or {})
    if normalized_format == "csv":
        return export_csv(events, filters or {})
    if normalized_format in {"ics", "ical", "icalendar"}:
        return export_ics(events, filters or {})
    raise ValueError(f"Unsupported export format: {format_name}")


def export_json(events: list[ApiEvent], filters: dict[str, Any]) -> ExportedFile:
    payload = ApiExportResponse(count=len(events), filters=filters, events=events)
    return ExportedFile(
        body=msgspec.json.encode(payload),
        content_type="application/json; charset=utf-8",
        filename=_export_filename(filters, "json"),
    )


def export_csv(events: list[ApiEvent], filters: dict[str, Any]) -> ExportedFile:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "date",
            "start_time",
            "end_time",
            "subject",
            "kind",
            "groups",
            "teachers",
            "places",
            "is_canceled",
        ]
    )
    for event in events:
        writer.writerow(
            [
                event.date.isoformat() if event.date else "",
                event.time_slot.start_time.isoformat(timespec="minutes")
                if event.time_slot and event.time_slot.start_time
                else "",
                event.time_slot.end_time.isoformat(timespec="minutes")
                if event.time_slot and event.time_slot.end_time
                else "",
                event.subject.name if event.subject else "",
                event.kind.name if event.kind else "",
                _join_names(event.groups),
                _join_names(event.teachers),
                "; ".join(place.display_name for place in event.places),
                "1" if event.is_canceled else "0",
            ]
        )
    return ExportedFile(
        body=output.getvalue().encode("utf-8-sig"),
        content_type="text/csv; charset=utf-8",
        filename=_export_filename(filters, "csv"),
    )


def export_ics(events: list[ApiEvent], filters: dict[str, Any]) -> ExportedFile:
    calendar = Calendar()
    calendar.add("prodid", "-//VSTU Schedule//API//RU")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "PUBLISH")

    for event in events:
        if not event.date:
            continue
        calendar_event = CalendarEvent()
        calendar_event.add("uid", f"event-{event.id}@vstu-schedule")
        calendar_event.add("dtstamp", datetime.now(UTC))
        calendar_event.add("dtstart", _event_datetime(event, end=False))
        calendar_event.add("dtend", _event_datetime(event, end=True))
        calendar_event.add("summary", event.subject.name if event.subject else "Schedule event")
        calendar_event.add("description", _event_description(event))
        calendar_event.add("location", "; ".join(place.display_name for place in event.places))
        calendar_event.add("status", "CANCELLED" if event.is_canceled else "CONFIRMED")
        calendar.add_component(calendar_event)

    return ExportedFile(
        body=calendar.to_ical(),
        content_type="text/calendar; charset=utf-8",
        filename=_export_filename(filters, "ics"),
    )


def _export_filename(filters: dict[str, Any], extension: str) -> str:
    reference_parts = _reference_filename_parts(filters)
    date_part = _date_filename_part(filters)
    parts = ["schedule", *reference_parts]
    if date_part and (not reference_parts or _is_specific_date_filter(filters)):
        parts.append(date_part)

    return f"{'_'.join(parts)}.{extension}"


def _reference_filename_parts(filters: dict[str, Any]) -> list[str]:
    parts = []
    for name, label in (
        ("group", "groups"),
        ("teacher", "teachers"),
        ("place", "rooms"),
        ("subject", "subjects"),
    ):
        values = filters.get(name)
        if isinstance(values, list) and values:
            parts.append(f"{label}_{_compact_values(values)}")
    return parts


def _date_filename_part(filters: dict[str, Any]) -> str:
    date_mode = str(filters.get("date") or "")
    left_date = str(filters.get("left_date") or "")
    right_date = str(filters.get("right_date") or "")
    if date_mode == "single_date" and left_date:
        return left_date
    if date_mode == "range_date" and left_date and right_date:
        return f"{left_date}_{right_date}"
    return date_mode if date_mode and date_mode != "today" else ""


def _is_specific_date_filter(filters: dict[str, Any]) -> bool:
    return str(filters.get("date") or "") in {"single_date", "range_date"}


def _compact_values(values: list[Any]) -> str:
    slugs = [_slugify_filename_part(str(value)) for value in values[:2]]
    if len(values) > 2:
        slugs.append(f"and-{len(values) - 2}-more")
    return "_".join(slug for slug in slugs if slug) or "selected"


def _slugify_filename_part(value: str) -> str:
    normalized = value.strip()
    normalized = re.sub(r"\s+", "-", normalized)
    normalized = re.sub(r"[^\w.-]+", "-", normalized, flags=re.UNICODE)
    normalized = normalized.strip("-_.")
    return normalized[:48] or "selected"


def _join_names(items: Iterable[object]) -> str:
    return "; ".join(getattr(item, "name", "") for item in items)


def _event_datetime(event: ApiEvent, *, end: bool) -> datetime:
    if event.date is None:
        raise ValueError("Cannot export event without date to iCalendar.")
    time_slot = event.time_slot
    time_value = None
    if time_slot:
        time_value = time_slot.end_time if end else time_slot.start_time
    if time_value is None:
        time_value = datetime.min.time().replace(hour=23 if end else 0, minute=59 if end else 0)
    return datetime.combine(event.date, time_value)


def _event_description(event: ApiEvent) -> str:
    parts = []
    if event.kind:
        parts.append(event.kind.name)
    if event.groups:
        parts.append(f"Группы: {_join_names(event.groups)}")
    if event.teachers:
        parts.append(f"Преподаватели: {_join_names(event.teachers)}")
    if event.is_canceled:
        parts.append("Отменено")
    return "\n".join(parts)
