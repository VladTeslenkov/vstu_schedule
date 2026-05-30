import logging
from typing import Any

from celery import signals
from django.utils import timezone

from apps.panel.models import CeleryTaskRun
from apps.panel.services.task_logging import (
    bind_task_logging_context,
    clear_task_logging_context,
)
from apps.panel.tasks import DISPATCH_CONFIGURED_TASK_NAME

logger = logging.getLogger(__name__)

_INTERNAL_TASKS = {DISPATCH_CONFIGURED_TASK_NAME}


def _should_track(task_name: str | None) -> bool:
    return bool(task_name) and task_name not in _INTERNAL_TASKS


def _stringify(value: Any, limit: int = 10000) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... truncated ..."


@signals.task_prerun.connect
def task_started(task_id: str, task: Any, **kwargs: Any) -> None:
    task_name = getattr(task, "name", "")
    if not _should_track(task_name):
        clear_task_logging_context()
        return

    bind_task_logging_context(task_id, task_name)
    CeleryTaskRun.objects.update_or_create(
        task_id=task_id,
        defaults={
            "task_name": task_name,
            "status": CeleryTaskRun.Status.STARTED,
            "started_at": timezone.now(),
        },
    )


@signals.task_postrun.connect
def task_finished(
    task_id: str,
    task: Any,
    retval: Any,
    state: str | None,
    **kwargs: Any,
) -> None:
    task_name = getattr(task, "name", "")
    if not _should_track(task_name):
        clear_task_logging_context()
        return

    try:
        status = state or CeleryTaskRun.Status.SUCCESS
        result_text = _stringify(retval)
        if isinstance(retval, dict) and retval.get("status") == "skipped":
            status = CeleryTaskRun.Status.SKIPPED
            result_text = retval.get("message") or result_text

        CeleryTaskRun.objects.update_or_create(
            task_id=task_id,
            defaults={
                "task_name": task_name,
                "status": status,
                "finished_at": timezone.now(),
                "result_text": result_text,
            },
        )
    finally:
        clear_task_logging_context()


@signals.task_failure.connect
def task_failed(
    task_id: str,
    exception: Exception,
    traceback: Any,
    sender: Any,
    **kwargs: Any,
) -> None:
    task_name = getattr(sender, "name", "")
    if not _should_track(task_name):
        return

    CeleryTaskRun.objects.update_or_create(
        task_id=task_id,
        defaults={
            "task_name": task_name,
            "status": CeleryTaskRun.Status.FAILURE,
            "finished_at": timezone.now(),
            "result_text": _stringify(exception),
            "traceback_text": _stringify(traceback, limit=20000),
        },
    )
    logger.warning("Celery task failed: %s [%s]", task_name, task_id)
