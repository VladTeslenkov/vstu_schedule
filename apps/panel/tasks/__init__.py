import json
import logging

from celery import shared_task
from django_celery_beat.models import PeriodicTask, IntervalSchedule

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="panel.tasks.update_timetable")
def update_timetable(self) -> dict:
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
        raise self.retry(exc=exc, max_retries=0)


@shared_task(bind=True, name="panel.tasks.clear_storage")
def clear_storage_task(self, component: str) -> dict:
    """
    Celery-задача: очистка компонента системы.
    Запускается вручную из панели управления.

    :param component: "Вся система", "Хранилище" или "База данных"
    """
    logger.info(f"Task started: clear_storage [component={component!r}, id={self.request.id}]")
    try:
        from apps.common.services.timetable_update.clear_storage import clear_storage_by_component
        clear_storage_by_component(component)
        logger.info(f"Task clear_storage completed: {component!r}")
        return {"status": "success", "component": component}
    except Exception as exc:
        logger.error(f"Task clear_storage failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, max_retries=0)


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
