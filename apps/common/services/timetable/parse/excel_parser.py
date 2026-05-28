from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vstuxls.cnf import DEFAULT_GRAMMAR, cnf_path
from vstuxls.converters.xlsx import ExcelGrid
from vstuxls.grammar2d import read_grammar
from vstuxls.services import DocumentParsingService


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
    content = document.get_content(include_position=False)
    if not isinstance(content, dict):
        raise ValueError("Parsed timetable document has unexpected content format.")

    title = _extract_title(content)
    event_payload = _build_event_payload(content, title)
    metadata = build_schedule_metadata(path, title, context)

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


def _build_event_payload(content: dict[str, Any], title: str) -> dict[str, Any]:
    table = content.get("table")
    if not isinstance(table, dict):
        raise ValueError("Parsed timetable document does not contain table data.")

    datetime_data = table.get("datetime")
    grid = table.get("grid")
    if not isinstance(datetime_data, dict) or not isinstance(grid, list):
        raise ValueError(
            "Parsed timetable table must contain datetime mapping and grid lesson list."
        )

    return {
        "title": title,
        "table": {
            "grid": grid,
            "datetime": datetime_data,
        },
    }


def _extract_title(content: dict[str, Any]) -> str:
    title = content.get("title")
    if isinstance(title, list):
        title = " ".join(str(part).strip() for part in title if str(part).strip())
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Parsed timetable document does not contain a title.")
    return _normalize_title(title)


def _normalize_title(title: str) -> str:
    title = title.replace("магистров", "магистратура").replace(
        "Магистров",
        "магистратура",
    )
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def _detect_faculty_shortname(text: str) -> str:
    upper_text = text.upper().replace("ФАСТиВ".upper(), "ФАСТИВ")
    for token, normalized in _FACULTY_ALIASES:
        if token in upper_text:
            return normalized
    return ""


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
