from datetime import datetime
import os
from pathlib import Path
import traceback
import shutil
import logging

from timetable_project.settings import TEMP_DIR, VIS_PATH
from timetable.models import Resource, FileVersion, Tag, Setting, Storage
from .parser import WebParser
from .storage_manager import StorageManager
from .view_changes import ViewChanges
from .file_data import FileData

# Создаем логгер для текущего модуля
logger = logging.getLogger(__name__)


class FileManager:
    # TIMETABLE_START_PATH = ["Расписания/Расписание занятий/","Расписания/Расписание экзаменов/"]
    TIMETABLE_START_PATH = ["Расписания/Расписание занятий/"]
    MIN_SEC_DELAY_UPDATE = 5
    MAX_SEC_DELAY_UPDATE = 10
    TIMETABLE_LINK = ""

    def __init__(self):
        # Задать новую директорию временных файлов
        os.environ["TMPDIR"] = str(TEMP_DIR)
        # Создать контейнер для хранилищ
        self.__storages = []
        # Взять путь к файлам из настроек
        try:
            self.TIMETABLE_LINK = Setting.objects.get(key="analyze_url").value.split(
                ";"
            )
            logger.info(f"Loaded timetable links from settings: {self.TIMETABLE_LINK}")
        except Setting.DoesNotExist:
            # self.TIMETABLE_LINK = ["https://www.vstu.ru/student/raspisaniya/zanyatiy/","https://www.vstu.ru/student/raspisaniya/exam/"]
            # self.TIMETABLE_LINK = ["http://localhost:8002/"]
            self.TIMETABLE_LINK = ["https://www.vstu.ru/student/raspisaniya/zanyatiy/"]
            logger.warning(
                "Setting 'analyze_url' not found, using default timetable links"
            )

    def add_storage(self, storage: StorageManager):
        """
        Добавить новое хранилище.
        :param storage: Хранилище файлов.
        """
        self.__storages.append(storage)
        logger.debug(f"Added storage: {storage.get_storage_type()}")

    def update_timetable(self):
        """
        Обновляет информацию о расписании
        :return:
        """
        logger.info("Starting timetable update process")
        used_resource_ids = set()
        # Получить все файлы с сайта
        for ind, el in enumerate(self.TIMETABLE_LINK):
            logger.info(
                f"Processing timetable link {ind+1}/{len(self.TIMETABLE_LINK)}: {el}"
            )
            files = WebParser.get_files_from_webpage(
                el, FileManager.TIMETABLE_START_PATH[ind]
            )
            logger.info(f"Found {len(files)} files from webpage")

            # Для всех файлов
            for file_data in files:
                logger.info(
                    f"Processing file - Path: {file_data.get_path()}, Name: {file_data.get_name()}"
                )

                try:
                    # Скачать файл
                    file_path = file_data.download_file(TEMP_DIR)
                    logger.debug(f"Downloaded file to: {file_path}")

                    # Конвертировать xls файл в xlsx файл, если это возможно
                    file_path = self.convert_xls_to_xlsx(file_path)
                    logger.debug(f"File after conversion: {file_path}")

                except Exception as e:
                    logger.error(
                        f"Error downloading or converting file: {e}", exc_info=True
                    )
                    continue

                # Рассчитать ресурс, которому соответствует файл
                if ind == 0:
                    resource = file_data.get_resource("Занятия")
                else:
                    resource = file_data.get_resource("Экзамены")

                # Рассчитать версию файла
                file_version = file_data.get_file_version(file_path)

                # Загрузить файл в хранилища, если подобного ресурса раньше не существовало
                resource_from_db = Resource.objects.filter(
                    path=resource.path, name=resource.name
                ).first()
                if resource_from_db:
                    file_version_from_db = FileVersion.objects.filter(
                        resource_id=resource_from_db.id
                    ).first()

                if (resource_from_db is None) or (
                    resource_from_db is not None
                    and file_version.url != file_version_from_db.url
                ):
                    logger.info(f"New resource found or URL changed: {resource.name}")

                    # Сохранить ресурс
                    resource.save()
                    # Сохранить информацию о версии
                    file_version.resource = resource
                    file_version.save()
                    # Загрузить файл во все доступные хранилища
                    self.save_file_to_storages(file_path, resource, file_version)
                else:
                    logger.debug(f"Resource already exists: {resource.name}")

                    # Обновить список тегов
                    tags = [
                        Tag.objects.get_or_create(name=tag.name, category=tag.category)[
                            0
                        ]
                        for tag in resource.get_not_saved_tags()
                    ]
                    resource_from_db.tags.set(tags)

                    # Выбрать уже существующий ресурс
                    resource = resource_from_db
                    resource.deprecated = False
                    resource.save()

                    # Найти последнюю запись с информацией о версии файла
                    file_version_from_db = (
                        FileVersion.objects.filter(resource=resource)
                        .order_by("-last_changed", "-timestamp")
                        .first()
                    )

                    # Создать новую версию файла, если запись не найдена или старая версия неактуальная
                    if (
                        file_version_from_db is None
                        or self.need_upload_new_file_version(
                            file_version, file_version_from_db
                        )
                    ):
                        logger.info(f"Creating new file version for: {resource.name}")

                        # Создать новую запись
                        file_version.resource = resource
                        file_version.save()

                        # Загрузить файл во все доступные хранилища
                        self.save_file_to_storages(file_path, resource, file_version)

                        # Подсветка изменений
                        self.on_file_version_changed(file_version)

                # Сохранить используемый ресурс
                used_resource_ids.add(resource.id)

                # Удалить временный файл
                if file_path.is_file():
                    file_path.unlink()
                    logger.debug(f"Temporary file deleted: {file_path}")

        # Если какие-то файлы были проанализированы, то все остальные файлы перевести в статус deprecated
        if used_resource_ids:
            deprecated_count = self.make_other_resource_deprecated(used_resource_ids)
            logger.info(f"Marked {deprecated_count} resources as deprecated")
        else:
            logger.warning("No files were processed during timetable update")

        logger.info("Timetable update process completed")

    def _download_from_storage(self, storage: StorageManager, local_path: Path):
        """
        Скачивает файл из хранилища во временную директорию
        """
        import requests

        logger.debug(
            f"Downloading file from storage {storage.get_storage_type()} to {local_path}"
        )
        response = requests.get(storage.download_url)
        if response.status_code == 200:
            with open(local_path, "wb") as f:
                f.write(response.content)
            logger.debug(f"Successfully downloaded file to {local_path}")
        else:
            error_msg = f"Failed to download file from {storage.download_url}, status code: {response.status_code}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def on_file_version_changed(self, file_version: FileVersion):
        logger.info(f"File version changed detected for: {file_version.resource.name}")
        # Создаем визуализацию изменений
        self.create_visualization(file_version)

    @classmethod
    def convert_xls_to_xlsx(cls, xls_file_path: Path | str, dell_xls=True):
        xls_path = Path(xls_file_path)

        if xls_path.suffix != ".xls":
            return xls_path

        xlsx_path = xls_path.with_suffix(".xlsx")
        # Нормализуем имя файла (убираем лишние точки)

        try:
            from xls2xlsx import XLS2XLSX

            converter = XLS2XLSX(str(xls_path))
            converter.to_xlsx(str(xlsx_path))
            if dell_xls:
                xls_path.unlink()
                logger.debug(
                    f"Converted {xls_path} to {xlsx_path} and deleted original"
                )
            else:
                logger.debug(f"Converted {xls_path} to {xlsx_path}")
            return xlsx_path
        except Exception as e:
            error_msg = f"Error converting XLS to XLSX: {e}"
            logger.error(error_msg, exc_info=True)
            return xls_path

    @staticmethod
    def need_upload_new_file_version(
        new_version: FileVersion, last_version: FileVersion
    ):
        """
        Определяет необходимость обновлять версию файла.
        :param new_version: Новая версия.
        :param last_version: Предыдущая версия.
        :return: Результат анализа.
        """
        need_update = new_version.hashsum != last_version.hashsum
        if need_update:
            logger.debug(
                f"File version update needed - hashsum changed: {last_version.hashsum} -> {new_version.hashsum}"
            )
        return need_update

    def save_file_to_storages(
        self, file_path: Path | str, resource: Resource, file_version: FileVersion
    ):
        """
        Сохранить файл во всех доступных хранилищах
        :param file_path:
        :param resource:
        :param file_version:
        :return:
        """
        # Приводим путь к файлу к нужному типу
        file_path = Path(file_path)
        logger.info(
            f"Saving file {file_path.name} to {len(self.__storages)} storage(s)"
        )

        for storage in self.__storages:
            logger.info(f"Uploading file to storage: {storage.get_storage_type()}")
            storage.add_new_file_version(file_path, resource, file_version)

    def make_other_resource_deprecated(self, used_resource_ids):
        resources = Resource.objects.exclude(id__in=used_resource_ids).filter(
            deprecated=False
        )
        count = 0
        for resource in resources:
            resource.deprecated = True
            resource.save()
            count += 1
        return count

    def create_visualization(self, f_version: FileVersion):
        """
        Создает визуализацию изменений между версиями файлов для указанного ресурса
        """
        logger.info(f"Creating visualization for resource: {f_version.resource.name}")
        resource = f_version.resource

        # Получаем все версии файла (кроме текущей)
        file_versions = (
            FileVersion.objects.filter(resource=resource, storages__isnull=False)
            .exclude(storages__path__contains="_Виз")
            .order_by("-last_changed")
            .distinct()
        )

        vis_path = VIS_PATH / Path(f"\{resource.name}_Виз.xlsx").name

        if len(file_versions) < 2:
            logger.info(
                f"Not enough file versions ({len(file_versions)}) to create visualization for {resource.name}"
            )
            return  # Нечего сравнивать

        logger.info(f"Found {len(file_versions)} file versions for comparison")

        # Получаем пути к файлам и даты изменений
        versions_to_compare = []
        for version in file_versions:
            storage = StorageManager.get_google_storage_by_file_version(version)
            if storage:
                local_path = TEMP_DIR / Path(storage.path).name
                if not local_path.exists():
                    # Скачиваем файл для сравнения
                    self._download_from_storage(storage, local_path)
                versions_to_compare.append((str(local_path), version.last_changed))

        if len(versions_to_compare) < 2:
            logger.warning(
                f"Not enough downloadable file versions ({len(versions_to_compare)}) for visualization"
            )
            return

        # Создаем визуализацию изменений
        logger.info(f"Creating visualization with {len(versions_to_compare)} versions")
        ViewChanges.view_changes(
            file_versions=versions_to_compare, output_file=vis_path, expiration_days=7
        )

        # Создаем новую версию файла с визуализацией
        vis_resource = FileData.get_vis_resource(resource)
        vis_resource.save()
        logger.info(f"Created visualization resource: {vis_resource.name}")

        # Создаем новую версию файла с визуализацией
        vis_file_version = FileData.get_vis_file_version(f_version, vis_resource)
        vis_file_version.save()
        logger.info(f"Created visualization file version")

        # Загружаем визуализированную версию во все хранилища
        self.save_file_to_storages(vis_path, vis_resource, vis_file_version)

        # Очищаем временную директорию
        if TEMP_DIR.exists():
            cleaned_files = self.clean_temp_directory()
            logger.debug(f"Cleaned {cleaned_files} temporary files")

    def clean_temp_directory(self):
        """Очищает временную директорию и возвращает количество удаленных файлов"""
        count = 0
        if TEMP_DIR.exists():
            for item in TEMP_DIR.iterdir():
                try:
                    if item.is_file():
                        item.unlink()
                        count += 1
                    elif item.is_dir():
                        shutil.rmtree(item)
                        count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete temporary item {item}: {e}")
        return count
