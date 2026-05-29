import inspect
import json
import logging
import re
import traceback
import uuid
from dataclasses import dataclass
from typing import Any, cast

from celery import current_app
from celery.result import AsyncResult
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from apps.panel.exceptions import PanelTaskConfigurationError
from apps.panel.models import CeleryTaskConfig, CeleryTaskLog, CeleryTaskRun
from apps.panel.services.task_metadata import TaskMetadata, get_task_metadata
from apps.panel.services.task_parameters import (
    celery_task_kwargs,
    coerce_task_parameters,
    raw_task_parameters_from_post,
)
from apps.panel.tasks import DISPATCH_CONFIGURED_TASK_NAME
from vstu_schedule.tasks.descriptors import get_task_descriptor

_CRON_VALUE_RE = re.compile(r"^[\d*,/\-]+$")
_INTERNAL_TASK_PREFIXES = ("celery.",)
_INTERNAL_TASKS = {DISPATCH_CONFIGURED_TASK_NAME}
_MANUAL_FAILED_TASK_ID_PREFIX = "manual-failed"
_STOPPABLE_STATUSES = {
    CeleryTaskRun.Status.PENDING,
    CeleryTaskRun.Status.STARTED,
    CeleryTaskRun.Status.RETRY,
}


@dataclass(frozen=True)
class RegisteredTask:
    name: str
    metadata: TaskMetadata
    config: CeleryTaskConfig
    can_run_without_args: bool
    required_arguments: list[str]
    latest_run: CeleryTaskRun | None
    latest_run_can_stop: bool
    schedule_enabled: bool


@dataclass(frozen=True)
class TaskParameterRow:
    descriptor: Any
    value: Any
    input_type: str


def _registered_task_names() -> list[str]:
    celery_app = cast(Any, current_app)
    celery_app.loader.import_default_modules()
    names = []
    for task_name in celery_app.tasks:
        if task_name in _INTERNAL_TASKS:
            continue
        if task_name.startswith(_INTERNAL_TASK_PREFIXES):
            continue
        descriptor = get_task_descriptor(task_name)
        if descriptor and descriptor.internal:
            continue
        names.append(task_name)
    return sorted(names)


def _required_arguments(task_name: str) -> list[str]:
    celery_app = cast(Any, current_app)
    task = celery_app.tasks[task_name]
    signature = inspect.signature(task.run)
    descriptor = get_task_descriptor(task_name)
    configured_parameters = (
        {parameter.name for parameter in descriptor.parameters} if descriptor else set()
    )
    required = []
    for name, parameter in signature.parameters.items():
        if name == "self":
            continue
        if name in configured_parameters:
            continue
        if parameter.default is not inspect.Parameter.empty:
            continue
        if parameter.kind not in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            continue
        required.append(name)
    return required


def _task_config(task_name: str) -> CeleryTaskConfig:
    config, created = CeleryTaskConfig.objects.get_or_create(task_name=task_name)
    if created:
        _apply_descriptor_defaults(config)
    return config


def _apply_descriptor_defaults(config: CeleryTaskConfig) -> None:
    descriptor = get_task_descriptor(config.task_name)
    if descriptor is None:
        return

    update_fields = []
    if descriptor.soft_time_limit_seconds:
        config.soft_time_limit_seconds = descriptor.soft_time_limit_seconds
        update_fields.append("soft_time_limit_seconds")
    if descriptor.time_limit_seconds:
        config.time_limit_seconds = descriptor.time_limit_seconds
        update_fields.append("time_limit_seconds")
    if descriptor.recommended_schedule:
        config.cron_minute = descriptor.recommended_schedule.minute
        config.cron_hour = descriptor.recommended_schedule.hour
        config.cron_day_of_week = descriptor.recommended_schedule.day_of_week
        config.cron_day_of_month = descriptor.recommended_schedule.day_of_month
        config.cron_month_of_year = descriptor.recommended_schedule.month_of_year
        update_fields.extend(
            [
                "cron_minute",
                "cron_hour",
                "cron_day_of_week",
                "cron_day_of_month",
                "cron_month_of_year",
            ]
        )

    if update_fields:
        config.save(update_fields=[*update_fields, "updated_at"])


def _periodic_task_for_task(
    task_name: str, config: CeleryTaskConfig | None = None
) -> PeriodicTask | None:
    if config and getattr(config, "periodic_task_id", None):
        return config.periodic_task
    direct_task = PeriodicTask.objects.filter(task=task_name).first()
    if direct_task:
        return direct_task
    return PeriodicTask.objects.filter(
        task=DISPATCH_CONFIGURED_TASK_NAME,
        args=json.dumps([task_name]),
    ).first()


def _schedule_enabled(task_name: str, config: CeleryTaskConfig) -> bool:
    periodic_task = _periodic_task_for_task(task_name, config)
    if periodic_task:
        return periodic_task.enabled
    return config.schedule_enabled


def _sync_periodic_task(config: CeleryTaskConfig) -> None:
    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute=config.cron_minute,
        hour=config.cron_hour,
        day_of_week=config.cron_day_of_week,
        day_of_month=config.cron_day_of_month,
        month_of_year=config.cron_month_of_year,
        timezone=settings.TIME_ZONE,
    )
    periodic_task = _periodic_task_for_task(config.task_name, config)
    task_name = (
        periodic_task.name if periodic_task else f"Panel configured task: {config.task_name}"
    )
    periodic_task, _ = PeriodicTask.objects.update_or_create(
        name=task_name,
        defaults={
            "task": DISPATCH_CONFIGURED_TASK_NAME,
            "crontab": schedule,
            "interval": None,
            "args": json.dumps([config.task_name]),
            "enabled": config.schedule_enabled,
        },
    )
    config.periodic_task = periodic_task
    config.save(update_fields=["periodic_task", "updated_at"])


def _validate_cron_value(value: str) -> str:
    value = value.strip() or "*"
    if not _CRON_VALUE_RE.match(value):
        raise PanelTaskConfigurationError("Cron fields may contain digits, *, /, - and commas.")
    return value


def _positive_int_or_none(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    number = int(value)
    if number <= 0:
        raise PanelTaskConfigurationError("Timeout must be greater than zero.")
    return number


def _apply_options(config: CeleryTaskConfig) -> dict[str, int]:
    options = {}
    if config.soft_time_limit_seconds:
        options["soft_time_limit"] = config.soft_time_limit_seconds
    if config.time_limit_seconds:
        options["time_limit"] = config.time_limit_seconds
    return options


def _apply_options_with_parameters(config: CeleryTaskConfig) -> dict[str, Any]:
    options: dict[str, Any] = _apply_options(config)
    descriptor = get_task_descriptor(config.task_name)
    if descriptor and descriptor.parameters:
        options["kwargs"] = celery_task_kwargs(descriptor.parameters, config.parameters)
    return options


def _record_failed_manual_task_run(
    config: CeleryTaskConfig,
    exception: Exception,
) -> CeleryTaskRun:
    now = timezone.now()
    message = f"Task was not queued: {exception}"
    run = CeleryTaskRun.objects.create(
        task_id=f"{_MANUAL_FAILED_TASK_ID_PREFIX}:{uuid.uuid4()}",
        task_name=config.task_name,
        status=CeleryTaskRun.Status.FAILURE,
        started_at=now,
        finished_at=now,
        result_text=str(exception),
        traceback_text=traceback.format_exc(),
    )
    CeleryTaskLog.objects.create(
        run=run,
        level=logging.ERROR,
        level_name="ERROR",
        logger_name=__name__,
        message=message,
        traceback_text=run.traceback_text,
    )
    return run


def _can_stop_task_run(run: CeleryTaskRun | None) -> bool:
    if run is None:
        return False
    if run.task_id.startswith(f"{_MANUAL_FAILED_TASK_ID_PREFIX}:"):
        return False
    return run.status in _STOPPABLE_STATUSES


def _record_task_run_log(
    run: CeleryTaskRun,
    *,
    level: int,
    level_name: str,
    message: str,
) -> None:
    CeleryTaskLog.objects.create(
        run=run,
        level=level,
        level_name=level_name,
        logger_name=__name__,
        message=message,
    )


def _stop_task_run(run: CeleryTaskRun) -> None:
    AsyncResult(run.task_id).revoke(terminate=True, signal="SIGTERM")
    run.status = CeleryTaskRun.Status.REVOKED
    run.finished_at = timezone.now()
    run.result_text = "Task was revoked from the admin panel."
    run.save(update_fields=["status", "finished_at", "result_text"])
    _record_task_run_log(
        run,
        level=logging.WARNING,
        level_name="WARNING",
        message="Task revoke requested from the admin panel.",
    )


def _task_parameter_rows(config: CeleryTaskConfig) -> list[TaskParameterRow]:
    descriptor = get_task_descriptor(config.task_name)
    if descriptor is None:
        return []
    input_types = {
        "int": "number",
        "float": "number",
        "date": "date",
        "datetime": "datetime-local",
        "time": "time",
        "url": "url",
        "path": "text",
        "str": "text",
    }
    return [
        TaskParameterRow(
            descriptor=parameter,
            value=config.parameters.get(parameter.name, parameter.default or ""),
            input_type=input_types.get(parameter.type, "text"),
        )
        for parameter in descriptor.parameters
    ]


def _task_parameters(config: CeleryTaskConfig) -> tuple[Any, ...]:
    descriptor = get_task_descriptor(config.task_name)
    return descriptor.parameters if descriptor else ()


def _task_rows() -> list[RegisteredTask]:
    rows = []
    latest_runs = {}
    for run in CeleryTaskRun.objects.order_by("-queued_at"):
        latest_runs.setdefault(run.task_name, run)
    for task_name in _registered_task_names():
        config = _task_config(task_name)
        required = _required_arguments(task_name)
        latest_run = latest_runs.get(task_name)
        rows.append(
            RegisteredTask(
                name=task_name,
                metadata=get_task_metadata(task_name),
                config=config,
                can_run_without_args=not required,
                required_arguments=required,
                latest_run=latest_run,
                latest_run_can_stop=_can_stop_task_run(latest_run),
                schedule_enabled=_schedule_enabled(task_name, config),
            )
        )
    return rows


@staff_member_required
def tasks_panel(request: HttpRequest) -> HttpResponse:
    return render(request, "panel/tasks.html", {"active_nav": "tasks", "tasks": _task_rows()})


@staff_member_required
def task_configure(request: HttpRequest, task_name: str) -> HttpResponse:
    if task_name not in _registered_task_names():
        return HttpResponse(status=404)

    config = _task_config(task_name)
    error = None

    if request.method == "POST":
        try:
            config.execution_enabled = request.POST.get("execution_enabled") == "on"
            config.schedule_enabled = request.POST.get("schedule_enabled") == "on"
            config.cron_minute = _validate_cron_value(request.POST.get("cron_minute", "0"))
            config.cron_hour = _validate_cron_value(request.POST.get("cron_hour", "*"))
            config.cron_day_of_week = _validate_cron_value(
                request.POST.get("cron_day_of_week", "*")
            )
            config.cron_day_of_month = _validate_cron_value(
                request.POST.get("cron_day_of_month", "*")
            )
            config.cron_month_of_year = _validate_cron_value(
                request.POST.get("cron_month_of_year", "*")
            )
            config.soft_time_limit_seconds = _positive_int_or_none(
                request.POST.get("soft_time_limit_seconds", "")
            )
            config.time_limit_seconds = _positive_int_or_none(
                request.POST.get("time_limit_seconds", "")
            )
            task_parameters = _task_parameters(config)
            if task_parameters:
                raw_parameters = raw_task_parameters_from_post(
                    task_parameters,
                    request.POST,
                )
                coerce_task_parameters(task_parameters, raw_parameters)
                config.parameters = raw_parameters
            config.save()
            _sync_periodic_task(config)
            return redirect("panel_tasks")
        except ValueError as exc:
            error = str(exc)

    return render(
        request,
        "panel/task_configure.html",
        {
            "config": config,
            "active_nav": "tasks",
            "task_name": task_name,
            "task_metadata": get_task_metadata(task_name),
            "task_parameter_rows": _task_parameter_rows(config),
            "required_arguments": _required_arguments(task_name),
            "schedule_enabled": _schedule_enabled(task_name, config),
            "error": error,
        },
    )


@staff_member_required
def task_run(request: HttpRequest, task_name: str) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)

    celery_app = cast(Any, current_app)
    task = celery_app.tasks.get(task_name)
    config = get_object_or_404(CeleryTaskConfig, task_name=task_name)
    if task is None or not config.execution_enabled or _required_arguments(task_name):
        return redirect("panel_tasks")

    try:
        result = task.apply_async(**_apply_options_with_parameters(config))
    except Exception as exc:
        run = _record_failed_manual_task_run(config, exc)
        run_id = cast(Any, run).id
        return redirect(
            f"{reverse('panel_task_log', kwargs={'task_name': task_name})}?run={run_id}"
        )

    CeleryTaskRun.objects.update_or_create(
        task_id=result.id,
        defaults={"task_name": task_name, "status": CeleryTaskRun.Status.PENDING},
    )
    return redirect(reverse("panel_task_log", kwargs={"task_name": task_name}))


@staff_member_required
def task_stop(request: HttpRequest, task_name: str) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)
    if task_name not in _registered_task_names():
        return HttpResponse(status=404)

    selected_id = request.POST.get("run")
    if selected_id:
        run = get_object_or_404(CeleryTaskRun, id=selected_id, task_name=task_name)
    else:
        run = (
            CeleryTaskRun.objects.filter(
                task_name=task_name,
                status__in=_STOPPABLE_STATUSES,
            )
            .order_by("-queued_at")
            .first()
        )
        if run is None:
            return redirect("panel_tasks")

    if _can_stop_task_run(run):
        _stop_task_run(run)

    run_id = cast(Any, run).id
    return redirect(f"{reverse('panel_task_log', kwargs={'task_name': task_name})}?run={run_id}")


@staff_member_required
def task_log(request: HttpRequest, task_name: str) -> HttpResponse:
    if task_name not in _registered_task_names():
        return HttpResponse(status=404)

    runs = list(CeleryTaskRun.objects.filter(task_name=task_name).order_by("-queued_at")[:100])
    selected_run = None
    selected_id = request.GET.get("run")
    if selected_id:
        selected_run = get_object_or_404(CeleryTaskRun, id=selected_id, task_name=task_name)
    elif runs:
        selected_run = runs[0]
    task_logs = list(CeleryTaskLog.objects.filter(run=selected_run)[:1000]) if selected_run else []

    return render(
        request,
        "panel/task_log.html",
        {
            "task_name": task_name,
            "task_metadata": get_task_metadata(task_name),
            "active_nav": "tasks",
            "runs": runs,
            "selected_run": selected_run,
            "selected_run_can_stop": _can_stop_task_run(selected_run),
            "task_logs": task_logs,
        },
    )
