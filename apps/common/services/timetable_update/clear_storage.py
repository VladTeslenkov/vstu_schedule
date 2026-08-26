import logging
import shutil

from django.conf import settings

from apps.common.models import FileVersion, Resource, Schedule, Tag

logger = logging.getLogger(__name__)


TASK_LOGS_COMPONENT = "Логи задач"
SCHEDULES_COMPONENT = "Расписания"


def clear_storage_by_component(component: str, *, preserve_task_id: str | None = None) -> None:
    """
    Очищает компонент системы по его имени.
    Вызывается из Celery-задачи panel.tasks.clear_storage.

    Допустимые значения: "Вся система", "Хранилище", "База данных", "Логи задач", "Расписания".
    """
    match component:
        case "Вся система":
            _clear_database()
            _clear_local_files()
        case "Хранилище":
            _clear_local_files()
        case "База данных":
            _clear_database()
        case _ if component == TASK_LOGS_COMPONENT:
            _clear_task_logs(preserve_task_id=preserve_task_id)
        case _ if component == SCHEDULES_COMPONENT:
            _clear_schedules()
        case _:
            logger.warning(f"Unknown component: {component!r}")
            raise ValueError(f"Неизвестный компонент: {component!r}")

    logger.info(f"Cleared: {component!r}")


def _clear_database() -> None:
    """Удаляет все записи FileVersion, Resource, Tag из БД."""
    FileVersion.objects.all().delete()
    Resource.objects.all().delete()
    Tag.objects.all().delete()
    logger.info("Database cleared")


def _clear_task_logs(*, preserve_task_id: str | None = None) -> None:
    """Удаляет сохранённые запуски задач и связанные с ними логи."""
    from apps.panel.models import CeleryTaskRun

    queryset = CeleryTaskRun.objects.all()
    if preserve_task_id:
        queryset = queryset.exclude(task_id=preserve_task_id)
    deleted_count, _ = queryset.delete()
    logger.info("Task logs cleared: %s records", deleted_count)


def _clear_schedules() -> None:
    """Удаляет все расписания."""
    deleted_count, _ = Schedule.objects.all().delete()
    logger.info("Schedules cleared: %s records", deleted_count)


def _clear_local_files() -> None:
    """Удаляет все файлы из DATA_STORAGE_DIR."""
    storage_dir = settings.DATA_STORAGE_DIR
    if not storage_dir.exists():
        logger.warning(f"Storage dir not found: {storage_dir}")
        return

    for item in storage_dir.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete {item}: {e}")

    logger.info(f"Local files cleared: {storage_dir}")
