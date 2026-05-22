import json
import logging
from typing import Any, cast

from celery import current_app
from django.conf import settings
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from vstu_schedule.tasks.decorators import project_task

logger = logging.getLogger(__name__)

DISPATCH_CONFIGURED_TASK_NAME = "panel.tasks.dispatch_configured_task"


def _task_apply_options(task_name: str) -> dict[str, int]:
    from apps.panel.models import CeleryTaskConfig

    config = CeleryTaskConfig.objects.filter(task_name=task_name).first()
    if not config:
        return {}

    options = {}
    if config.soft_time_limit_seconds:
        options["soft_time_limit"] = config.soft_time_limit_seconds
    if config.time_limit_seconds:
        options["time_limit"] = config.time_limit_seconds
    return options


@project_task(name=DISPATCH_CONFIGURED_TASK_NAME)
def dispatch_configured_task(self: Any, task_name: str) -> dict[str, str]:
    """Queue a configured task using the latest DB settings."""
    from apps.panel.models import CeleryTaskConfig

    config = CeleryTaskConfig.objects.filter(task_name=task_name).first()
    if not config or not config.execution_enabled:
        logger.info("Configured task dispatch skipped: %s", task_name)
        return {"status": "skipped", "task": task_name}

    celery_app = cast(Any, current_app)
    task = celery_app.tasks.get(task_name)
    if task is None:
        raise ValueError(f"Celery task is not registered: {task_name}")

    result = task.apply_async(**_task_apply_options(task_name))
    logger.info(
        "Configured task dispatched: %s [dispatcher_id=%s, task_id=%s]",
        task_name,
        self.request.id,
        result.id,
    )
    return {"status": "queued", "task": task_name, "task_id": result.id}


@project_task(name="panel.tasks.update_timetable", max_retries=3)
def update_timetable(self: Any) -> dict[str, str]:
    """
    Celery-задача: скачивает файлы расписания и сохраняет новые версии локально.
    Запускается периодически через Celery Beat.
    Может быть запущена вручную из панели управления.
    """
    logger.info(f"Task started: update_timetable [id={self.request.id}]")
    try:
        from apps.common.services.timetable_update.update_timetable import run_timetable_update

        run_timetable_update()
        logger.info("Task update_timetable completed")
        return {"status": "success"}
    except Exception as exc:
        logger.error(f"Task update_timetable failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60) from exc


@project_task(name="panel.tasks.clear_storage")
def clear_storage_task(self: Any, component: str) -> dict[str, str]:
    """
    Celery-задача: очистка компонента системы.
    Запускается вручную из панели управления.

    :param component: "Вся система", "Хранилище" или "База данных"
    """
    logger.info(f"Task started: clear_storage [component={component!r}, id={self.request.id}]")
    try:
        from apps.common.services.timetable_update.clear_storage import (
            clear_storage_by_component,
        )

        clear_storage_by_component(component)
        logger.info(f"Task clear_storage completed: {component!r}")
        return {"status": "success", "component": component}
    except Exception as exc:
        logger.error(f"Task clear_storage failed: {exc}", exc_info=True)
        raise


def configure_periodic_update(interval_minutes: int) -> None:
    """
    Создаёт или обновляет периодическую задачу обновления расписания в Celery Beat.
    Вызывается из view при сохранении настроек.

    :param interval_minutes: интервал запуска в минутах
    """
    from apps.panel.models import CeleryTaskConfig

    task_name = update_timetable.name
    config, _ = CeleryTaskConfig.objects.get_or_create(task_name=task_name)
    config.execution_enabled = True
    config.schedule_enabled = True
    config.cron_minute = "0"
    config.cron_hour = f"*/{interval_minutes // 60}" if interval_minutes >= 60 else "*"
    config.cron_day_of_week = "*"
    config.cron_day_of_month = "*"
    config.cron_month_of_year = "*"
    config.save()

    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute=config.cron_minute,
        hour=config.cron_hour,
        day_of_week=config.cron_day_of_week,
        day_of_month=config.cron_day_of_month,
        month_of_year=config.cron_month_of_year,
        timezone=settings.TIME_ZONE,
    )
    periodic_task, _ = PeriodicTask.objects.update_or_create(
        name="Автообновление расписания",
        defaults={
            "task": DISPATCH_CONFIGURED_TASK_NAME,
            "crontab": schedule,
            "interval": None,
            "args": json.dumps([task_name]),
            "enabled": True,
        },
    )
    config.periodic_task = periodic_task
    config.save(update_fields=["periodic_task", "updated_at"])
    logger.info(f"Periodic update configured: every {interval_minutes} min")
