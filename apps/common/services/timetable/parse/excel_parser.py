from __future__ import annotations

import contextlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vstuxls.cnf import DEFAULT_GRAMMAR, cnf_path
from vstuxls.converters.xlsx import ExcelGrid
from vstuxls.grammar2d import read_grammar
from vstuxls.grammar2d.Match2d import Match2d
from vstuxls.services import DocumentParsingService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TimetableImportContext:
    academic_year: str
    semester: int
    semester_start_date: str
    semester_end_date: str
    starting_day_number: int = 0


@dataclass(frozen=True)
class ParsedTimetable:
    source_path: Path
    title: str
    schedule_metadata: dict[str, Any]
    event_payload: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


_FACULTY_ALIASES: tuple[tuple[str, str], ...] = (
    ("ФЭВТ", "ФЭВТ"),
    ("ХТФ", "ХТФ"),
    ("ХФ", "ХТФ"),
    ("ФЭУ", "ФЭУ"),
    ("ФТПП", "ФТПП"),
    ("ФАТ", "ФАТ"),
    ("ФАСТИВ", "ФАСТИВ"),
    ("ФТКМ", "ФТКМ"),
    ("ВМЦЭ", "ВМЦЭ"),
)

_WEEK_DAYS = [
    "ПОНЕДЕЛЬНИК",
    "ВТОРНИК",
    "СРЕДА",
    "ЧЕТВЕРГ",
    "ПЯТНИЦА",
    "СУББОТА",
]


def parse_timetable_excel(path: Path, context: TimetableImportContext) -> ParsedTimetable:
    grid = ExcelGrid.read_xlsx(path)
    with cnf_path(DEFAULT_GRAMMAR) as grammar_path:
        grammar = read_grammar(str(grammar_path))
    if grammar is None:
        raise ValueError(f"Could not read bundled VSTU XLS grammar: {DEFAULT_GRAMMAR}")

    service = DocumentParsingService(grammar=grammar)
    documents = service.parse_document(grid)
    if not documents:
        raise ValueError(f"Could not parse timetable document: {path}")

    document = documents[0]
    title = _extract_title(document)
    metadata = build_schedule_metadata(path, title, context)
    event_payload = _build_event_payload(document, title, metadata)

    return ParsedTimetable(
        source_path=path,
        title=title,
        schedule_metadata=metadata,
        event_payload=event_payload,
    )


def build_schedule_metadata(
    source_path: Path,
    original_title: str,
    context: TimetableImportContext,
) -> dict[str, Any]:
    faculty = _detect_faculty_shortname(source_path.name) or _detect_faculty_shortname(
        original_title
    )
    if not faculty:
        raise ValueError(
            f"Could not detect faculty shortname from {source_path.name!r} or title {original_title!r}."
        )

    return {
        "course": _detect_course(source_path.name, original_title),
        "schedule_template_metadata_faculty_shortname": faculty,
        "semester": context.semester,
        "years": context.academic_year,
        "start_date": context.semester_start_date,
        "end_date": context.semester_end_date,
        "scope": _detect_scope(source_path, original_title),
        "department_shortname": faculty,
        "starting_day_number": context.starting_day_number,
        "original_title": original_title,
    }


def _build_event_payload(
    matched_document: Match2d,
    title: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    weeks, months = _extract_weeks(matched_document["table"]["datetime"])
    payload = {
        "title": _normalize_title(
            title,
            str(metadata.get("scope") or ""),
            str(metadata["semester"]),
            str(metadata["years"]),
        ),
        "table": {
            "grid": _extract_lessons(matched_document, years=str(metadata["years"])),
            "datetime": {
                "weeks": weeks,
                "week_days": _WEEK_DAYS,
                "months": months,
            },
        },
    }
    return _apply_post_fixes(payload, metadata)


def _extract_title(matched_document: Match2d) -> str:
    title = _plain(matched_document["title"].get_text())
    if not title.strip():
        raise ValueError("Parsed timetable document does not contain a title.")
    return _normalize_title(title)


def _plain(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(str(item) for item in value)
    return str(value)


def _parse_year_bounds(years_text: str | None) -> tuple[int, int]:
    match = re.search(r"(\d{4})\s*[-–—]\s*(\d{4})", years_text or "")
    if not match:
        raise ValueError(f"Could not parse academic year bounds from {years_text!r}.")
    return int(match.group(1)), int(match.group(2))


def _normalize_faculty_spelling(text: str) -> str:
    return re.sub(r"(?i)фастив", "ФАСТИВ", text)


def _detect_faculty_shortname(text: str) -> str:
    upper_text = _normalize_faculty_spelling(text).upper()
    for token, normalized in _FACULTY_ALIASES:
        if token in upper_text:
            return normalized
    return ""


def _normalize_title(
    original_title: str,
    scope_word: str | None = None,
    current_semester: str | None = None,
    academic_year: str | None = None,
) -> str:
    title = (original_title or "").strip()
    if not title:
        return ""

    title = title.replace("магистров", "магистратура").replace(
        "Магистров",
        "магистратура",
    )
    title = _normalize_faculty_spelling(title)

    if academic_year:
        title = re.sub(r"\b20\d{2}\s*[-–—]\s*20\d{2}\b", academic_year, title)

    if current_semester:
        title = re.sub(
            r"\b\d\s*[-й]*\s*семестр\b",
            f"{current_semester} семестр",
            title,
            flags=re.IGNORECASE,
        )

    normalized_scope = (scope_word or "").strip()
    lower_title = title.lower()
    scopes = ("бакалавриат", "магистратура", "аспирантура")
    if "бакалавриат" in lower_title and "магистратура" in lower_title:
        cleaned = title
        for scope in scopes:
            cleaned = re.sub(rf"\b{scope}\b", "", cleaned, flags=re.IGNORECASE)
        title = f"{re.sub(r'\s{2,}', ' ', cleaned).strip(' ,;')} магистратура".strip()
        lower_title = title.lower()

    scope_missing = normalized_scope and normalized_scope.lower() not in lower_title
    scope_conflicts_with_master = (
        normalized_scope.lower() == "бакалавриат" and "магистратура" in lower_title
    )
    if scope_missing and not scope_conflicts_with_master:
        title = f"{title} {normalized_scope}".strip()

    return re.sub(r"\s+", " ", title).strip()


def _detect_scope(source_path: Path, title: str) -> str:
    text = " ".join([*(source_path.parts), title]).lower()
    if "магистратура" in text or "магистр" in text:
        return "магистратура"
    if "аспирантура" in text or "аспирант" in text:
        return "Аспирантура"
    if "консульт" in text:
        return "консультация"
    return "бакалавриат"


def _detect_course(filename: str, title: str) -> str:
    for text in (filename, title):
        match = re.search(r"(\d)\s*(?:-|й|ый|ого|курс)", text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    match = re.search(r"\d", filename)
    if match:
        return match.group(0)
    raise ValueError(f"Could not detect course from {filename!r} or title {title!r}.")


def _index_of_weekday(name: str) -> int:
    assert name in _WEEK_DAYS, f"{name} not in {_WEEK_DAYS}"
    return _WEEK_DAYS.index(name)


def _name_of_week(index: int) -> str | None:
    return {1: "first_week", 2: "second_week"}.get(index)


def _extract_weeks(datetime_match: Match2d) -> tuple[dict, list[str]]:
    raw_month_names = datetime_match["month_names"].get_content()
    if not isinstance(raw_month_names, list):
        raise ValueError("Parsed timetable datetime month_names must be a list.")
    month_names = [str(month) for month in raw_month_names]

    def index_of_month(name: str) -> int:
        assert name in month_names, f"{name} not in {month_names}"
        return month_names.index(name)

    def make_calendar_for_weekday(month_days_match: Match2d) -> list[dict]:
        out_calendar: list[dict] = []

        def add(month: str, day_number: str) -> None:
            month_index = index_of_month(month)
            for calendar_month_info in out_calendar:
                if calendar_month_info["month_index"] == month_index:
                    calendar_month_info["month_days"].append(day_number)
                    break
            else:
                out_calendar.append(
                    {
                        "month_index": month_index,
                        "month_days": [day_number],
                    }
                )

        for month_days in month_days_match["month_days"].get_children():
            for month_day in month_days.get_children():
                add(
                    _plain(month_day["month_name"].get_text()),
                    _plain(month_day["month_day"].get_text()),
                )
        return out_calendar

    out_weeks: dict[str, list[dict]] = {}
    for week in datetime_match["weeks"].get_children():
        content = week.get_content()
        if not isinstance(content, dict):
            continue
        week_index = content.get("@index_in_array")
        if not isinstance(week_index, int):
            continue
        week_name = _name_of_week(week_index)
        if not week_name:
            continue

        days_info = [
            {
                "week_day_index": _index_of_weekday(_plain(day["week_day"].get_text())),
                "calendar": make_calendar_for_weekday(day),
            }
            for day in week["_days"].get_children()
        ]
        out_weeks.setdefault(week_name, []).extend(days_info)

    return out_weeks, month_names


def _normalize_single_date(raw_value: str, years_hint: str) -> list[str]:
    raw = (raw_value or "").strip()
    if not raw:
        return []

    left_year, right_year = _parse_year_bounds(years_hint)

    def resolve_year(month: int) -> int:
        return left_year if month > 6 else right_year

    glued_match = re.fullmatch(r"(\d{1,2}\.\d{1,2})\.(\d{1,2}\.\d{1,2})", raw)
    if glued_match:
        return _normalize_single_date(
            glued_match.group(1),
            years_hint,
        ) + _normalize_single_date(glued_match.group(2), years_hint)

    day_year_month_match = re.fullmatch(r"(\d{1,2})\.(\d{4})\.(\d{1,2})", raw)
    if day_year_month_match:
        day, year, month = day_year_month_match.groups()
        raw = f"{day}.{month}.{year}"

    full_match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", raw)
    if full_match:
        day = int(full_match.group(1))
        month = int(full_match.group(2))
        year = int(full_match.group(3))
        if 1 <= day <= 31 and 1 <= month <= 12:
            return [f"{day:02d}.{month:02d}.{year:04d}"]
        if 1 <= day <= 12 and 13 <= month <= 31:
            return [f"{month:02d}.{day:02d}.{year:04d}"]
        return []

    partial_match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})", raw.rstrip("."))
    if partial_match:
        day = int(partial_match.group(1))
        month = int(partial_match.group(2))
        if 1 <= day <= 31 and 1 <= month <= 12:
            return [f"{day:02d}.{month:02d}.{resolve_year(month):04d}"]
    return []


def _normalize_dates_list(values: list[str], years_hint: str) -> list[str]:
    out: list[str] = []
    for value in values:
        for token in re.split(r"[;,]|\.\.+|\s+", value or ""):
            token = token.strip()
            if token:
                out.extend(_normalize_single_date(token, years_hint))

    seen: set[str] = set()
    result: list[str] = []
    for date_value in out:
        if date_value not in seen:
            seen.add(date_value)
            result.append(date_value)
    return result


def _cleanup_teacher_name(name: str) -> str:
    cleaned = (name or "").strip()
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" ;,")


def _audience_compare_key(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").strip()).upper()


def _dedupe_places_preserving_order(places: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for place in places:
        raw = (place or "").strip()
        if not raw:
            continue
        key = _audience_compare_key(raw)
        if key not in seen:
            seen.add(key)
            out.append(raw)
    return out


def _strip_teachers_duplicating_places(teachers: list[str], places: list[str]) -> list[str]:
    place_keys = {_audience_compare_key(place) for place in places if place and str(place).strip()}
    out: list[str] = []
    for teacher in teachers:
        raw = (teacher or "").strip()
        if raw and _audience_compare_key(raw) not in place_keys:
            out.append(_cleanup_teacher_name(raw))
    return out


def _extract_dates_from_place(value: str, years_hint: str) -> tuple[list[str], str]:
    text = (value or "").strip()
    if not text:
        return [], ""
    date_like = re.findall(r"\d{1,2}\.\d{1,2}(?:\.\d{4})?", text)
    dates = _normalize_dates_list(date_like, years_hint) if date_like else []
    if not dates:
        return [], text
    cleaned = re.sub(r"\d{1,2}\.\d{1,2}(?:\.\d{4})?", " ", text)
    cleaned = re.sub(r"[;,.]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,;")
    if re.fullmatch(r"\d+", cleaned or ""):
        cleaned = ""
    return dates, cleaned


def _apply_post_fixes(payload: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    years_hint = str(metadata["years"])
    payload["title"] = _normalize_title(
        str(payload.get("title", "")),
        str(metadata.get("scope") or ""),
        str(metadata.get("semester") or ""),
        str(metadata.get("years") or ""),
    )

    for lesson in payload.get("table", {}).get("grid", []):
        participants = lesson.get("participants", {})
        teachers = participants.get("teachers", [])
        participants["teachers"] = [
            _cleanup_teacher_name(teacher) for teacher in teachers if str(teacher).strip()
        ]
        lesson["participants"] = participants

        holds = lesson.get("holds_on_date", []) or []
        holds_norm = (
            _normalize_dates_list([str(value) for value in holds], years_hint)
            if isinstance(holds, list)
            else _normalize_dates_list([str(holds)], years_hint)
        )

        new_places: list[str] = []
        extra_dates: list[str] = []
        for place in lesson.get("places", []) or []:
            found_dates, cleaned_place = _extract_dates_from_place(str(place), years_hint)
            extra_dates.extend(found_dates)
            if cleaned_place:
                new_places.append(cleaned_place)
        new_places = _dedupe_places_preserving_order(new_places)
        lesson["places"] = new_places
        lesson["holds_on_date"] = _normalize_dates_list(holds_norm + extra_dates, years_hint)
        participants["teachers"] = _strip_teachers_duplicating_places(
            participants.get("teachers", []),
            new_places,
        )
        lesson["participants"] = participants

    return payload


def _extract_lessons(matched_document: Match2d, years: str) -> list[dict]:
    groups_content = matched_document["table"]["groups"].get_content()
    if not isinstance(groups_content, dict):
        raise ValueError("Parsed timetable groups must be a mapping.")
    raw_groups = groups_content.get("groups")
    if not isinstance(raw_groups, list):
        raise ValueError("Parsed timetable groups must contain a groups list.")
    group_names = [str(group) for group in raw_groups]

    def resolve_groups(discipline_match: Match2d) -> list[str]:
        discipline_content = discipline_match.get_content()

        def append_group_value(raw_value: Any, into: list[str]) -> None:
            if isinstance(raw_value, str) and raw_value.strip():
                into.append(raw_value.strip())
            elif isinstance(raw_value, dict) and "group" in raw_value:
                append_group_value(raw_value["group"], into)

        def collect_groups_from_content(content: Any, into: list[str]) -> None:
            if isinstance(content, dict):
                if "group" in content:
                    append_group_value(content["group"], into)
                if "groups" in content and isinstance(content["groups"], list):
                    for group in content["groups"]:
                        append_group_value(group, into)
                if "first_group" in content and "last_group" in content:
                    first = content["first_group"]
                    last = content["last_group"]
                    if (
                        isinstance(first, dict)
                        and isinstance(last, dict)
                        and "group" in first
                        and "group" in last
                    ):
                        with contextlib.suppress(ValueError):
                            start = group_names.index(first["group"])
                            end = group_names.index(last["group"])
                            into.extend(group_names[start : end + 1])
                for key, value in content.items():
                    if re.fullmatch(r"m\d+", str(key)):
                        collect_groups_from_content(value, into)
            elif isinstance(content, list):
                for item in content:
                    collect_groups_from_content(item, into)

        if isinstance(discipline_content, dict):
            if "group" in discipline_content:
                return [discipline_content["group"]["group"]]
            if "first_group" in discipline_content and "last_group" in discipline_content:
                start = group_names.index(discipline_content["first_group"]["group"])
                end = group_names.index(discipline_content["last_group"]["group"])
                return group_names[start : end + 1]
            if "groups" in discipline_content:
                return discipline_content["groups"]

            collected: list[str] = []
            collect_groups_from_content(discipline_content, collected)
            if collected:
                seen: set[str] = set()
                out: list[str] = []
                for group in collected:
                    if group not in seen:
                        seen.add(group)
                        out.append(group)
                return out

        raise ValueError(f"Cannot extract groups: unknown discipline format {discipline_content!r}")

    def extract_teachers(lesson_match: Match2d) -> list[str]:
        teachers = []
        if "teacher" in lesson_match:
            teacher_content = lesson_match["teacher"].get_content()
            if isinstance(teacher_content, list):
                for item in teacher_content:
                    if isinstance(item, str) and item.strip():
                        teachers.append(item.strip())
                    elif isinstance(item, dict) and "teacher" in item:
                        teachers.append(_plain(item["teacher"]))
            elif isinstance(teacher_content, dict):
                if "teacher" in teacher_content:
                    teachers.append(_plain(teacher_content["teacher"]))
                if "teachers" in teacher_content:
                    teachers.extend(_plain(teacher) for teacher in teacher_content["teachers"])
            elif isinstance(teacher_content, str) and teacher_content.strip():
                teachers.append(teacher_content.strip())

        if not teachers and "frame" in lesson_match:
            frame_content = lesson_match["frame"].get_content()
            if isinstance(frame_content, dict) and isinstance(frame_content.get("teacher"), str):
                teachers.append(frame_content["teacher"].strip())

        return [teacher for teacher in teachers if teacher]

    def extract_rooms(lesson_match: Match2d) -> list[str]:
        rooms = []
        if "room" in lesson_match:
            room_content = lesson_match["room"].get_content()
            if isinstance(room_content, list):
                for item in room_content:
                    if isinstance(item, str) and item.strip():
                        rooms.append(item.strip())
                    elif isinstance(item, dict) and "room" in item:
                        rooms.append(_plain(item["room"]))
            elif isinstance(room_content, dict):
                if "room" in room_content:
                    rooms.append(_plain(room_content["room"]))
                if "rooms" in room_content:
                    rooms.extend(_plain(room) for room in room_content["rooms"])
            elif isinstance(room_content, str) and room_content.strip():
                rooms.append(room_content.strip())

        if not rooms and "frame" in lesson_match:
            frame_content = lesson_match["frame"].get_content()
            if isinstance(frame_content, dict) and isinstance(frame_content.get("room"), str):
                rooms.append(frame_content["room"].strip())

        normalized_rooms = []
        for room in rooms:
            value = room.strip()
            while "--" in value:
                value = value.replace("--", "-")
            if value:
                normalized_rooms.append(value)
        return normalized_rooms

    def extract_kind(lesson_match: Match2d, hours: list[str]) -> str:
        def raw_kind_text() -> str | None:
            if "frame" in lesson_match:
                frame_match = lesson_match["frame"]
                if isinstance(frame_match, Match2d) and "_explicit_lesson_kind" in frame_match:
                    return _plain(frame_match["_explicit_lesson_kind"].get_text())
            for key in ("lesson_kind", "_explicit_lesson_kind"):
                if key in lesson_match and isinstance(lesson_match[key], Match2d):
                    return _plain(lesson_match[key].get_text())
            return None

        text = raw_kind_text()
        if text:
            lowered = text.lower()
            if "лаб" in lowered:
                return "лабораторная работа"
            if "пр." in lowered or "практ" in lowered:
                return "практика"
            if "лек" in lowered:
                return "лекция"

        height = lesson_match.box.h if lesson_match.box else None
        if len(hours or []) >= 2 and height is not None and height >= 6:
            return "лабораторная работа"
        return "лекция"

    def extract_hours(lesson_match: Match2d) -> list[str]:
        hours = []
        if "explicit_hours" in lesson_match:
            content = lesson_match["explicit_hours"].get_content()
            if isinstance(content, dict) and "hour_range" in content:
                hours.append(_plain(content["hour_range"]))
            elif isinstance(content, str):
                hours.append(content)

        if not hours and "frame" in lesson_match:
            frame_content = lesson_match["frame"].get_content()
            if isinstance(frame_content, dict):
                for key in ("hour_begin", "hour_end"):
                    value = frame_content.get(key)
                    if isinstance(value, dict) and "hour_range" in value:
                        hours.append(_plain(value["hour_range"]))
                    elif isinstance(value, str):
                        hours.append(value)
                if not hours:
                    hour_1 = frame_content.get("hour_1")
                    if isinstance(hour_1, dict) and "hour_range" in hour_1:
                        hours.append(_plain(hour_1["hour_range"]))
                    elif isinstance(hour_1, str):
                        hours.append(hour_1)
                if not hours and isinstance(frame_content.get("discipline"), dict):
                    hour_begin = frame_content["discipline"].get("hour_begin")
                    if isinstance(hour_begin, dict) and "hour_range" in hour_begin:
                        hours.append(_plain(hour_begin["hour_range"]))
                    elif isinstance(hour_begin, str):
                        hours.append(hour_begin)

        if not hours:
            raise ValueError("Cannot extract hours: unknown lesson format")
        return hours

    def normalize_hour_ranges(hours: list[str]) -> list[str]:
        result: list[str] = []
        for raw in hours:
            if not raw:
                continue
            value = raw.strip()
            if re.fullmatch(r"\d{1,2}\s*-\s*\d{1,2}", value):
                start, end = [part.strip() for part in value.split("-", 1)]
                result.append(f"{int(start)}-{int(end)}")
                continue

            nums = [int(number) for number in re.findall(r"\d+", value)]
            if len(nums) == 2:
                start, end = nums
                if end > start and (end - start + 1) % 2 == 0:
                    current = start
                    while current < end:
                        result.append(f"{current}-{current + 1}")
                        current += 2
                else:
                    result.append(f"{start}-{end}")
                continue
            result.append(value)
        return result

    def extract_discipline(lesson_match: Match2d) -> tuple[str, list[str]]:
        if "frame" not in lesson_match or "discipline" not in lesson_match["frame"]:
            raise ValueError("Discipline not found in lesson frame")

        discipline_match = lesson_match["frame"]["discipline"]
        discipline_content = discipline_match.get_content()

        def extract_discipline_parts(value: Any) -> list[str]:
            if isinstance(value, str):
                return [value.strip()] if value.strip() else []
            if isinstance(value, list):
                parts: list[str] = []
                for item in value:
                    parts.extend(extract_discipline_parts(item))
                return parts
            if isinstance(value, dict):
                if "discipline" in value:
                    return extract_discipline_parts(value["discipline"])
                if "discipline_name" in value:
                    return extract_discipline_parts(value["discipline_name"])
                parts: list[str] = []
                for key in sorted(
                    [key for key in value if re.fullmatch(r"m\d+", str(key))],
                    key=lambda item: int(str(item)[1:]),
                ):
                    parts.extend(extract_discipline_parts(value[key]))
                return parts
            return []

        parts = extract_discipline_parts(discipline_content)
        subject = " ".join(part for part in parts if part)
        if not subject:
            raise ValueError(f"Cannot extract discipline subject from: {discipline_content!r}")

        return subject, resolve_groups(discipline_match)

    def extract_week_info(
        lesson_match: Match2d,
        datetime_match: Match2d,
    ) -> tuple[int, str]:
        week_day_index = 0
        week = "first_week"

        if "frame" in lesson_match:
            frame_content = lesson_match["frame"].get_content()
            if isinstance(frame_content, dict):
                for hour_key in ("hour_begin",):
                    hour_begin = frame_content.get(hour_key)
                    if isinstance(hour_begin, dict) and "week_day" in hour_begin:
                        with contextlib.suppress(ValueError, AssertionError):
                            week_day_index = _index_of_weekday(_plain(hour_begin["week_day"]))
                if week_day_index == 0 and isinstance(frame_content.get("discipline"), dict):
                    hour_begin = frame_content["discipline"].get("hour_begin")
                    if isinstance(hour_begin, dict) and "week_day" in hour_begin:
                        with contextlib.suppress(ValueError, AssertionError):
                            week_day_index = _index_of_weekday(_plain(hour_begin["week_day"]))

        if datetime_match and lesson_match.box and "weeks" in datetime_match:
            week_children = datetime_match["weeks"].get_children()
            if len(week_children) >= 2:
                week1 = week_children[0]
                week2 = week_children[1]
                if week1.box and week2.box:
                    is_first_week = lesson_match.box.top < week1.box.bottom
                    target_week = week1 if is_first_week else week2
                    default_week = "first_week" if is_first_week else "second_week"
                    week_content = target_week.get_content()
                    if isinstance(week_content, dict) and "@index_in_array" in week_content:
                        week = _name_of_week(week_content["@index_in_array"]) or default_week
            elif week_children:
                week_content = week_children[0].get_content()
                if isinstance(week_content, dict) and "@index_in_array" in week_content:
                    week = _name_of_week(week_content["@index_in_array"]) or week

        return week_day_index, week

    def extract_explicit_dates(lesson_match: Match2d) -> list[str]:
        dates = []
        if "explicit_dates" not in lesson_match:
            return dates

        content = lesson_match["explicit_dates"].get_content()
        if isinstance(content, list):
            for item in content:
                if isinstance(item, str):
                    for date_part in item.replace("\\n", "\n").split("\n"):
                        dates.extend(date.strip() for date in date_part.split(",") if date.strip())
                elif isinstance(item, dict) and "date" in item:
                    dates.append(_plain(item["date"]))
        elif isinstance(content, dict):
            if "dates" in content:
                dates.extend(_plain(date) for date in content["dates"])
            elif "date" in content:
                dates.append(_plain(content["date"]))
        elif isinstance(content, str):
            for date_part in content.replace("\\n", "\n").split("\n"):
                dates.extend(date.strip() for date in date_part.split(",") if date.strip())
        return dates

    out_lessons = []
    grid_match = matched_document["table"]["grid"]
    datetime_match = matched_document["table"]["datetime"]

    for lesson_match in grid_match.get_children():
        try:
            subject, groups = extract_discipline(lesson_match)
            teachers = extract_teachers(lesson_match)
            rooms = extract_rooms(lesson_match)
            hours = normalize_hour_ranges(extract_hours(lesson_match))
            week_day_index, week = extract_week_info(lesson_match, datetime_match)
            explicit_dates = _normalize_dates_list(extract_explicit_dates(lesson_match), years)

            out_lessons.append(
                {
                    "subject": subject,
                    "kind": extract_kind(lesson_match, hours),
                    "participants": {
                        "teachers": teachers,
                        "student_groups": groups,
                    },
                    "places": rooms,
                    "hours": hours,
                    "week_day_index": week_day_index,
                    "week": week,
                    "holds_on_date": explicit_dates,
                }
            )
        except Exception:
            logger.warning(
                "Could not extract lesson from parsed timetable.",
                exc_info=True,
            )
            continue

    return out_lessons
