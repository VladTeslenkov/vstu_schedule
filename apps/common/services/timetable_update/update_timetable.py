from pathlib import Path
from django.core.management.base import BaseCommand
import logging

from timetable_project.settings import DATA_STORAGE_DIR, VIS_PATH, GOOGLE_AUTH_FILE
from timetable.apps import GOOGLE_DRIVE_STORAGE_MAME, LOCAL_STORAGE_NAME

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Запуск обновления данных"

    @staticmethod
    def update_timetable():
        logger.info("Запущена задача обновления расписания")

        # Добавить все необходимые библиотеки
        from .version_core.storage_manager_google_drive import StorageManagerGoogleDrive
        from .version_core.storage_manager import StorageManager
        from .version_core.filemanager import FileManager

        import fs.copy

        # Путь к корневой папке локального хранилища
        local_dir = DATA_STORAGE_DIR
        Path(local_dir).mkdir(exist_ok=True)
        viz_dir = Path(local_dir) / "ВИЗ"
        viz_dir.mkdir(exist_ok=True)
        logger.debug(f"Созданы директории: {local_dir} и {viz_dir}")

        local_fs = fs.open_fs(str(local_dir))
        logger.debug("Локальная файловая система инициализирована")

        # TODO : Перенести в FileManager
        # Создать хранилища
        sm_google = StorageManagerGoogleDrive(
            GOOGLE_DRIVE_STORAGE_MAME, GOOGLE_AUTH_FILE
        )
        logger.info(f"Создано Google Drive хранилище: {GOOGLE_DRIVE_STORAGE_MAME}")

        sm_local = StorageManager(LOCAL_STORAGE_NAME, local_fs)
        logger.info(f"Создано локальное хранилище: {LOCAL_STORAGE_NAME}")

        # Создать класс управления файлами
        file_manager = FileManager()
        logger.debug("Создан FileManager")

        # Добавить в него проинициализированные хранилища
        file_manager.add_storage(sm_local)
        # file_manager.add_storage(sm_google)
        logger.info("Хранилища добавлены в FileManager")

        # Выполнить обновление файлов
        logger.info("Запуск процесса обновления расписания")
        file_manager.update_timetable()

        logger.info("Задача обновления расписания выполнена успешно!")

    def handle(self, *args, **kwargs):
        logger.info("Обработка команды обновления расписания")
        try:
            self.update_timetable()
            logger.info("Команда обновления расписания завершена успешно")
        except Exception as e:
            logger.error(
                f"Ошибка при выполнении команды обновления расписания: {e}",
                exc_info=True,
            )
            raise
