from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskLoggingContext:
    task_id: str
    task_name: str


_task_logging_context: ContextVar[TaskLoggingContext | None] = ContextVar(
    "task_logging_context",
    default=None,
)


def bind_task_logging_context(task_id: str, task_name: str) -> None:
    _task_logging_context.set(TaskLoggingContext(task_id=task_id, task_name=task_name))


def clear_task_logging_context() -> None:
    _task_logging_context.set(None)


def current_task_logging_context() -> TaskLoggingContext | None:
    return _task_logging_context.get()


class CeleryTaskLogHandler(logging.Handler):
    """Persist Python log records emitted during a tracked Celery task run."""

    def emit(self, record: logging.LogRecord) -> None:
        context = current_task_logging_context()
        if context is None:
            return

        try:
            from apps.panel.models import CeleryTaskLog, CeleryTaskRun

            run = CeleryTaskRun.objects.only("id").filter(task_id=context.task_id).first()
            if run is None:
                return

            formatter = self.formatter or logging.Formatter()
            traceback_text = ""
            if record.exc_info:
                traceback_text = formatter.formatException(record.exc_info)

            CeleryTaskLog.objects.create(
                run=run,
                level=record.levelno,
                level_name=record.levelname,
                logger_name=record.name,
                message=record.getMessage(),
                traceback_text=traceback_text,
                process=record.process,
                thread=record.thread,
                pathname=record.pathname,
                lineno=record.lineno,
            )
        except Exception:
            self.handleError(record)
