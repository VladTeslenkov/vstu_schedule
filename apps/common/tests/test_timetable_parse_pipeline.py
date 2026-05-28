from datetime import date, datetime, time
from pathlib import Path

import pytest

from apps.common.services.timetable.parse.excel_parser import (
    TimetableImportContext,
    build_schedule_metadata,
)
from apps.common.services.timetable.parse.pipeline import _local_file_candidates
from apps.panel.services.task_parameters import celery_task_kwargs, coerce_task_parameters
from vstu_schedule.tasks.descriptors import TaskParameterDescriptor


def _parameter(name: str, type_: str, *, required: bool = False, default=None):
    return TaskParameterDescriptor(
        name=name,
        type=type_,
        label={"en": name},
        description={},
        required=required,
        default=default,
    )


def test_task_parameter_type_coercion():
    descriptors = (
        _parameter("name", "str"),
        _parameter("count", "int"),
        _parameter("ratio", "float"),
        _parameter("enabled", "bool"),
        _parameter("day", "date"),
        _parameter("moment", "datetime"),
        _parameter("at", "time"),
        _parameter("folder", "path"),
        _parameter("endpoint", "url"),
    )

    result = coerce_task_parameters(
        descriptors,
        {
            "name": "demo",
            "count": "7",
            "ratio": "1.5",
            "enabled": "on",
            "day": "2026-02-09",
            "moment": "2026-02-09T12:30:00",
            "at": "12:30",
            "folder": "data/import",
            "endpoint": "https://example.test/import",
        },
    )

    assert result["name"] == "demo"
    assert result["count"] == 7
    assert result["ratio"] == 1.5
    assert result["enabled"] is True
    assert result["day"] == date(2026, 2, 9)
    assert result["moment"] == datetime(2026, 2, 9, 12, 30)
    assert result["at"] == time(12, 30)
    assert result["folder"] == Path("data/import")
    assert result["endpoint"] == "https://example.test/import"


def test_required_task_parameter_missing():
    with pytest.raises(ValueError, match="required"):
        coerce_task_parameters((_parameter("academic_year", "str", required=True),), {})


def test_celery_task_kwargs_are_json_safe():
    result = celery_task_kwargs(
        (
            _parameter("day", "date"),
            _parameter("at", "time"),
            _parameter("folder", "path"),
        ),
        {
            "day": "2026-02-09",
            "at": "12:30",
            "folder": "data/import",
        },
    )

    assert result == {
        "day": "2026-02-09",
        "at": "12:30:00",
        "folder": str(Path("data/import")),
    }


def test_schedule_metadata_uses_context_values():
    metadata = build_schedule_metadata(
        source_path=Path("imports/Магистратура/ФЭВТ 2 курс.xlsx"),
        original_title="Учебные занятия ФЭВТ магистратура 2 курса",
        context=TimetableImportContext(
            academic_year="2025-2026",
            semester=2,
            semester_start_date="09.02.2026",
            semester_end_date="30.06.2026",
            starting_day_number=7,
        ),
    )

    assert metadata["schedule_template_metadata_faculty_shortname"] == "ФЭВТ"
    assert metadata["department_shortname"] == "ФЭВТ"
    assert metadata["scope"] == "магистратура"
    assert metadata["course"] == "2"
    assert metadata["years"] == "2025-2026"
    assert metadata["semester"] == 2
    assert metadata["start_date"] == "09.02.2026"
    assert metadata["end_date"] == "30.06.2026"
    assert metadata["starting_day_number"] == 7


def test_local_file_candidates_include_converted_mimetype_suffix():
    candidates = _local_file_candidates(
        Path("data") / "resource",
        "schedule.xls",
        ".xlsx",
    )

    assert candidates == [
        Path("data") / "resource" / "schedule.xls",
        Path("data") / "resource" / "schedule.xlsx",
    ]
