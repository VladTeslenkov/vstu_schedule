from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from vstu_schedule.tasks.descriptors import TaskParameterDescriptor

_TRUE_VALUES = {"1", "true", "yes", "on", "y"}
_FALSE_VALUES = {"0", "false", "no", "off", "n"}


def coerce_task_parameter(descriptor: TaskParameterDescriptor, value: Any) -> Any:
    if value is None or value == "":
        if descriptor.required:
            raise ValueError(f"Task parameter {descriptor.name!r} is required.")
        return descriptor.default

    match descriptor.type:
        case "str":
            return str(value)
        case "int":
            return int(value)
        case "float":
            return float(value)
        case "bool":
            if isinstance(value, bool):
                return value
            normalized = str(value).strip().lower()
            if normalized in _TRUE_VALUES:
                return True
            if normalized in _FALSE_VALUES:
                return False
            raise ValueError(f"Task parameter {descriptor.name!r} must be a boolean.")
        case "date":
            if isinstance(value, date) and not isinstance(value, datetime):
                return value
            return date.fromisoformat(str(value))
        case "datetime":
            if isinstance(value, datetime):
                return value
            return datetime.fromisoformat(str(value))
        case "time":
            if isinstance(value, time):
                return value
            return time.fromisoformat(str(value))
        case "path":
            return Path(str(value))
        case "url":
            parsed = urlparse(str(value))
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"Task parameter {descriptor.name!r} must be an HTTP URL.")
            return str(value)
        case _:
            raise ValueError(f"Unsupported task parameter type: {descriptor.type}")


def coerce_task_parameters(
    descriptors: tuple[TaskParameterDescriptor, ...],
    values: dict[str, Any] | None,
) -> dict[str, Any]:
    values = values or {}
    return {
        descriptor.name: coerce_task_parameter(descriptor, values.get(descriptor.name))
        for descriptor in descriptors
    }


def celery_task_kwargs(
    descriptors: tuple[TaskParameterDescriptor, ...],
    values: dict[str, Any] | None,
) -> dict[str, Any]:
    parameters = coerce_task_parameters(descriptors, values)
    serializable = {}
    for key, value in parameters.items():
        if isinstance(value, date | datetime | time):
            serializable[key] = value.isoformat()
        elif isinstance(value, Path):
            serializable[key] = str(value)
        else:
            serializable[key] = value
    return serializable


def raw_task_parameters_from_post(
    descriptors: tuple[TaskParameterDescriptor, ...],
    post_data: Any,
) -> dict[str, Any]:
    parameters = {}
    for descriptor in descriptors:
        field_name = f"param_{descriptor.name}"
        if descriptor.type == "bool":
            parameters[descriptor.name] = field_name in post_data
        else:
            parameters[descriptor.name] = post_data.get(field_name, "")
    return parameters
