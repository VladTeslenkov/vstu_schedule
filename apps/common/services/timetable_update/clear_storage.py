import logging
import shutil

from django.conf import settings

from apps.common.models import Resource, FileVersion, Tag

logger = logging.getLogger(__name__)


def clear_storage_by_component(component: str) -> None:
    """
    Очищает компонент системы по его имени.
    Вызывается из Celery-задачи panel.tasks.clear_storage.

    Допустимые значения: "Вся система", "Хранилище", "База данных".
    """
    match component:
        case "Вся система":
            _clear_database()
            _clear_local_files()
        case "Хранилище":
            _clear_local_files()
        case "База данных":
            _clear_database()
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
