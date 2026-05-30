import logging
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from celery import current_app
from django.apps import apps as django_apps
from django.core.checks import Warning as CheckWarning

logger = logging.getLogger(__name__)

TASK_DESCRIPTOR_FILENAME = "tasks.toml"
_INTERNAL_TASK_PREFIXES = ("celery.",)
TASK_CONCURRENCY_PARALLEL = "parallel"
TASK_CONCURRENCY_SINGLETON = "singleton"
TASK_CONCURRENCY_EXCLUSIVE = "exclusive"
TASK_CONCURRENCY_CHOICES = frozenset(
    {
        TASK_CONCURRENCY_PARALLEL,
        TASK_CONCURRENCY_SINGLETON,
        TASK_CONCURRENCY_EXCLUSIVE,
    }
)
TASK_PARAMETER_TYPES = frozenset(
    {
        "str",
        "int",
        "float",
        "bool",
        "date",
        "datetime",
        "time",
        "path",
        "url",
    }
)


@dataclass(frozen=True)
class TaskScheduleDescriptor:
    minute: str = "0"
    hour: str = "*"
    day_of_week: str = "*"
    day_of_month: str = "*"
    month_of_year: str = "*"


@dataclass(frozen=True)
class TaskParameterDescriptor:
    name: str
    type: str
    label: dict[str, str]
    description: dict[str, str]
    required: bool = False
    default: Any = None


@dataclass(frozen=True)
class TaskDescriptor:
    task_name: str
    app_label: str
    name: dict[str, str]
    description: dict[str, str]
    soft_time_limit_seconds: int | None = None
    time_limit_seconds: int | None = None
    recommended_schedule: TaskScheduleDescriptor | None = None
    parameters: tuple[TaskParameterDescriptor, ...] = ()
    concurrency: str = TASK_CONCURRENCY_EXCLUSIVE
    internal: bool = False


def task_descriptor_path(app_path: Path) -> Path:
    return app_path / "tasks" / TASK_DESCRIPTOR_FILENAME


def _optional_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    number = int(value)
    if number <= 0:
        raise ValueError("Task timeout values must be greater than zero.")
    return number


def _translations(value: Any, field_name: str, task_name: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{task_name}.{field_name} must be an inline table.")
    return {str(language): str(text) for language, text in value.items()}


def _schedule(value: Any, task_name: str) -> TaskScheduleDescriptor | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{task_name}.recommended_schedule must be an inline table.")
    return TaskScheduleDescriptor(
        minute=str(value.get("minute", "0")),
        hour=str(value.get("hour", "*")),
        day_of_week=str(value.get("day_of_week", "*")),
        day_of_month=str(value.get("day_of_month", "*")),
        month_of_year=str(value.get("month_of_year", "*")),
    )


def _concurrency(value: Any, task_name: str) -> str:
    if value is None:
        return TASK_CONCURRENCY_EXCLUSIVE
    concurrency = str(value)
    if concurrency not in TASK_CONCURRENCY_CHOICES:
        allowed = ", ".join(sorted(TASK_CONCURRENCY_CHOICES))
        raise ValueError(f"{task_name}.concurrency must be one of: {allowed}.")
    return concurrency


def _parameters(value: Any, task_name: str) -> tuple[TaskParameterDescriptor, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{task_name}.parameters must be an array of TOML tables.")

    parameters = []
    names = set()
    for raw_parameter in value:
        if not isinstance(raw_parameter, dict):
            raise ValueError(f"{task_name}.parameters entries must be TOML tables.")
        name = str(raw_parameter.get("name", "")).strip()
        if not name:
            raise ValueError(f"{task_name}.parameters entries must have a name.")
        if name in names:
            raise ValueError(f"{task_name}.parameters contains duplicate parameter: {name}.")
        names.add(name)

        parameter_type = str(raw_parameter.get("type", "str"))
        if parameter_type not in TASK_PARAMETER_TYPES:
            allowed = ", ".join(sorted(TASK_PARAMETER_TYPES))
            raise ValueError(f"{task_name}.{name}.type must be one of: {allowed}.")

        parameters.append(
            TaskParameterDescriptor(
                name=name,
                type=parameter_type,
                label=_translations(raw_parameter.get("label", {"en": name}), "label", name),
                description=_translations(
                    raw_parameter.get("description", {}),
                    "description",
                    name,
                ),
                required=bool(raw_parameter.get("required", False)),
                default=raw_parameter.get("default"),
            )
        )
    return tuple(parameters)


def _parse_descriptor_file(path: Path, app_label: str) -> dict[str, TaskDescriptor]:
    with path.open("rb") as file:
        config = tomllib.load(file)

    descriptors = {}
    for task_name, task_config in config.items():
        if not isinstance(task_config, dict):
            raise ValueError(f"{path}: {task_name} must be a TOML table.")
        descriptor = TaskDescriptor(
            task_name=task_name,
            app_label=app_label,
            name=_translations(task_config.get("name"), "name", task_name),
            description=_translations(task_config.get("description", {}), "description", task_name),
            soft_time_limit_seconds=_optional_positive_int(
                task_config.get("soft_time_limit_seconds")
            ),
            time_limit_seconds=_optional_positive_int(task_config.get("time_limit_seconds")),
            recommended_schedule=_schedule(task_config.get("recommended_schedule"), task_name),
            parameters=_parameters(task_config.get("parameters"), task_name),
            concurrency=_concurrency(task_config.get("concurrency"), task_name),
            internal=bool(task_config.get("internal", False)),
        )
        descriptors[task_name] = descriptor
    return descriptors


@lru_cache(maxsize=1)
def task_descriptors() -> dict[str, TaskDescriptor]:
    descriptors = {}
    for app_config in django_apps.get_app_configs():
        path = task_descriptor_path(Path(app_config.path))
        if not path.exists():
            continue
        try:
            descriptors.update(_parse_descriptor_file(path, app_config.label))
        except (OSError, tomllib.TOMLDecodeError, TypeError, ValueError):
            logger.warning("Could not load Celery task descriptors from %s", path, exc_info=True)
    return descriptors


def get_task_descriptor(task_name: str) -> TaskDescriptor | None:
    return task_descriptors().get(task_name)


def _project_task_prefixes() -> tuple[str, ...]:
    prefixes = []
    for app_config in django_apps.get_app_configs():
        if app_config.name.startswith("apps."):
            prefixes.append(f"{app_config.label}.tasks.")
            prefixes.append(f"{app_config.name}.tasks.")
    return tuple(prefixes)


def registered_project_task_names(*, import_default_modules: bool = True) -> list[str]:
    celery_app = cast(Any, current_app)
    if import_default_modules:
        celery_app.loader.import_default_modules()
    prefixes = _project_task_prefixes()
    names = []
    for task_name in celery_app.tasks:
        if task_name.startswith(_INTERNAL_TASK_PREFIXES):
            continue
        if prefixes and not task_name.startswith(prefixes):
            continue
        names.append(task_name)
    return sorted(names)


def warn_about_missing_task_descriptors() -> None:
    try:
        missing = missing_task_descriptor_names()
    except Exception:
        logger.warning("Could not validate Celery task descriptors.", exc_info=True)
        return

    for task_name in missing:
        logger.warning(
            "Celery task %s has no descriptor. Add it to the app tasks/%s file.",
            task_name,
            TASK_DESCRIPTOR_FILENAME,
        )


def missing_task_descriptor_names(*, import_default_modules: bool = True) -> list[str]:
    descriptors = task_descriptors()
    return [
        task_name
        for task_name in registered_project_task_names(
            import_default_modules=import_default_modules
        )
        if task_name not in descriptors
    ]


def task_descriptor_system_check(app_configs: Any, **kwargs: Any) -> list[CheckWarning]:
    try:
        missing = missing_task_descriptor_names(import_default_modules=False)
    except Exception as exc:
        return [
            CheckWarning(
                f"Could not validate Celery task descriptors: {exc}",
                id="common.W001",
            )
        ]
    return [
        CheckWarning(
            f"Celery task {task_name} has no descriptor. "
            f"Add it to the app tasks/{TASK_DESCRIPTOR_FILENAME} file.",
            id="common.W002",
        )
        for task_name in missing
    ]
