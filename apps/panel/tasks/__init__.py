import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from celery import shared_task
from django.conf import settings
from django_celery_beat.models import IntervalSchedule, PeriodicTask
from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

_MAINTENANCE_LOCK_NAME = "vstu_schedule:panel:maintenance"
_MAINTENANCE_LOCK_TIMEOUT_SECONDS = 6 * 60 * 60


@contextmanager
def _maintenance_lock(task_name: str) -> Iterator[bool]:
    client = Redis.from_url(settings.CELERY_BROKER_URL)
    lock = client.lock(_MAINTENANCE_LOCK_NAME, timeout=_MAINTENANCE_LOCK_TIMEOUT_SECONDS)
    acquired = lock.acquire(blocking=False)
    if not acquired:
        logger.warning("Task skipped because another maintenance task is running: %s", task_name)
        yield False
        return

    try:
        yield True
    finally:
        try:
            lock.release()
        except RedisError:
            logger.warning(
                "Could not release maintenance lock for task: %s", task_name, exc_info=True
            )


@shared_task(bind=True, name="panel.tasks.update_timetable", max_retries=3)
def update_timetable(self: Any) -> dict[str, str]:
    """
    Celery-задача: скачивает файлы расписания и сохраняет новые версии локально.
    Запускается периодически через Celery Beat.
    Может быть запущена вручную из панели управления.
    """
    logger.info(f"Task started: update_timetable [id={self.request.id}]")
    try:
        with _maintenance_lock("update_timetable") as acquired:
            if not acquired:
                return {
                    "status": "skipped",
                    "reason": "maintenance_task_running",
                    "message": "Another maintenance task is already running.",
                }

            from apps.common.services.timetable_update.update_timetable import run_timetable_update

            run_timetable_update()
        logger.info("Task update_timetable completed")
        return {"status": "success"}
    except Exception as exc:
        logger.error(f"Task update_timetable failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60) from exc


@shared_task(bind=True, name="panel.tasks.clear_storage")
def clear_storage_task(self: Any, component: str) -> dict[str, str]:
    """
    Celery-задача: очистка компонента системы.
    Запускается вручную из панели управления.

    :param component: "Вся система", "Хранилище" или "База данных"
    """
    logger.info(f"Task started: clear_storage [component={component!r}, id={self.request.id}]")
    try:
        with _maintenance_lock("clear_storage") as acquired:
            if not acquired:
                return {
                    "status": "skipped",
                    "reason": "maintenance_task_running",
                    "message": "Another maintenance task is already running.",
                }

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
    schedule, _ = IntervalSchedule.objects.get_or_create(
        every=interval_minutes,
        period=IntervalSchedule.MINUTES,
    )
    PeriodicTask.objects.update_or_create(
        name="Автообновление расписания",
        defaults={
            "task": "panel.tasks.update_timetable",
            "interval": schedule,
            "args": json.dumps([]),
            "enabled": True,
        },
    )
    logger.info(f"Periodic update configured: every {interval_minutes} min")
