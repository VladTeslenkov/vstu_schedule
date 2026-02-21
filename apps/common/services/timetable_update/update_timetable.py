import logging

logger = logging.getLogger(__name__)


def run_timetable_update() -> None:
    """
    Точка входа для запуска обновления расписания.
    Вызывается из Celery-задачи (apps/panel/tasks) или management command.
    """
    logger.info("Запуск обновления расписания")

    from django.conf import settings
    from apps.common.services.timetable_update.version_core.filemanager import FileManager

    # Убедиться, что нужные директории существуют
    settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
    settings.DATA_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    file_manager = FileManager()
    file_manager.update_timetable()

    logger.info("Обновление расписания завершено")
