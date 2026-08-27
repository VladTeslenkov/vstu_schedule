import logging
import os
import shutil
from pathlib import Path
from typing import ClassVar

from django.conf import settings

from apps.common.models import FileVersion, Resource, Setting

from .file_data import FileData
from .parser import WebParser

logger = logging.getLogger(__name__)


class FileManager:
    """
    Управляет процессом обновления расписания:
    скачивает файлы с сайта, сравнивает с предыдущими версиями,
    сохраняет новые файлы локально и создаёт записи в БД.
    """

    TIMETABLE_START_PATH: ClassVar = ["Расписания/Расписание занятий/"]

    def __init__(self) -> None:
        self._temp_dir: Path = settings.TEMP_DIR
        self._storage_dir: Path = settings.DATA_STORAGE_DIR
        os.environ["TMPDIR"] = str(self._temp_dir)

        try:
            self._timetable_links: list[str] = Setting.objects.get(key="analyze_url").value.split(
                ";"
            )
            logger.info(f"Loaded timetable links: {self._timetable_links}")
        except Setting.DoesNotExist:
            self._timetable_links = ["https://www.vstu.ru/student/raspisaniya/zanyatiy/"]
            logger.warning("Setting 'analyze_url' not found, using default")

    def update_timetable(self) -> None:
        """
        Основной метод: обходит все ссылки, скачивает файлы,
        проверяет изменения и сохраняет новые версии.
        """
        logger.info("Starting timetable update")
        used_resource_ids: set[int] = set()

        for ind, link in enumerate(self._timetable_links):
            logger.info(f"Processing link {ind + 1}/{len(self._timetable_links)}: {link}")
            files = WebParser.get_files_from_webpage(link, self.TIMETABLE_START_PATH[ind])
            logger.info(f"Found {len(files)} files")

            for file_data in files:
                logger.info(f"Processing: {file_data.get_path()} / {file_data.get_name()}")

                try:
                    file_path = file_data.download_file(self._temp_dir)
                    # Хэш считаем по исходному скачанному файлу — до конвертации .xls в .xlsx,
                    # т.к. xls2xlsx/openpyxl при каждой пересборке пишет новые временные метки
                    # в метаданные и ZIP-записи, из-за чего хэш "плавает" при неизменном содержимом.
                    new_version = file_data.get_file_version(file_path)
                    file_path = self._convert_xls_to_xlsx(file_path)
                    new_version.mimetype = file_path.suffix
                except Exception as e:
                    logger.error(f"Failed to download/convert file: {e}", exc_info=True)
                    continue

                resource_type = "Занятия" if ind == 0 else "Экзамены"

                try:
                    resource = self._process_file(file_data, file_path, new_version, resource_type)
                    if resource:
                        used_resource_ids.add(resource.id)
                except Exception as e:
                    logger.error(
                        f"Failed to process file {file_data.get_name()}: {e}", exc_info=True
                    )
                finally:
                    if file_path.is_file():
                        file_path.unlink()

        deprecated_count = self._mark_deprecated(used_resource_ids)
        if deprecated_count:
            logger.info(f"Marked {deprecated_count} resources as deprecated")

        logger.info("Timetable update completed")

    # ------------------- ПРИВАТНЫЕ МЕТОДЫ ------------------- #

    def _process_file(
        self, file_data: FileData, file_path: Path, new_version: FileVersion, resource_type: str
    ) -> Resource | None:
        """
        Обрабатывает скачанный файл:
        - получает или создаёт Resource
        - сравнивает URL и хэш с последней версией
        - если файл изменился — сохраняет локально и создаёт FileVersion
        """
        new_resource = file_data.get_resource(resource_type)
        new_version.file_name = file_path.name

        resource_from_db = Resource.objects.filter(
            path=new_resource.path, name=new_resource.name
        ).first()

        # Новый ресурс — сохраняем сразу
        if resource_from_db is None:
            logger.info(f"New resource: {new_resource.name}")
            new_resource.save()
            new_version.resource = new_resource
            new_version.save()
            self._save_file_locally(file_path, new_resource)
            return new_resource

        # Ресурс существует — снимаем deprecated если был
        resource = resource_from_db
        if resource.deprecated:
            resource.deprecated = False
            resource.save()

        last_version = (
            FileVersion.objects.filter(resource=resource)
            .order_by("-last_changed", "-timestamp")
            .first()
        )

        # URL изменился или версий ещё нет — создаём новую версию
        if last_version is None or last_version.url != new_version.url:
            logger.info(f"URL changed or no version exists for: {resource.name}")
            if last_version:
                self._archive_file(resource, last_version)
            new_version.resource = resource
            new_version.save()
            self._save_file_locally(file_path, resource)
            return resource

        # URL тот же — проверяем хэш
        if last_version.hashsum != new_version.hashsum:
            logger.info(f"Hash changed for: {resource.name}")
            self._archive_file(resource, last_version)
            new_version.resource = resource
            new_version.save()
            self._save_file_locally(file_path, resource)
        else:
            logger.info(f"No changes detected for: {resource.name}")

        return resource

    def _save_file_locally(self, file_path: Path, resource: Resource) -> Path:
        """Сохраняет файл в DATA_STORAGE_DIR по пути ресурса."""
        dest_dir = self._storage_dir / (resource.path or resource.name)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / file_path.name
        shutil.copy2(file_path, dest_file)
        logger.debug(f"File saved to: {dest_file}")
        return dest_file

    def _archive_file(self, resource: Resource, version: FileVersion) -> None:
        """
        Переименовывает текущий файл версии на диске, добавляя в имя
        дату изменения (last_changed, либо timestamp как fallback),
        и помечает версию как заархивированную.
        """
        if version.archived or not version.file_name:
            return

        dest_dir = self._storage_dir / (resource.path or resource.name)
        current_file = dest_dir / version.file_name

        if not current_file.is_file():
            logger.warning(f"Archive skipped, file not found: {current_file}")
            return

        date_source = version.last_changed or version.timestamp
        date_stamp = date_source.strftime("%Y-%m-%d")
        archived_name = f"{current_file.stem}_{date_stamp}{current_file.suffix}"
        archived_path = dest_dir / archived_name

        counter = 1
        while archived_path.exists():
            archived_path = (
                dest_dir / f"{current_file.stem}_{date_stamp}_{counter}{current_file.suffix}"
            )
            counter += 1

        current_file.rename(archived_path)

        version.file_name = archived_path.name
        version.archived = True
        version.save(update_fields=["file_name", "archived"])

        logger.info(f"Archived file: {current_file.name} -> {archived_path.name}")

    @staticmethod
    def _convert_xls_to_xlsx(file_path: Path) -> Path:
        """Конвертирует .xls в .xlsx через xls2xlsx. Если не .xls — возвращает исходный файл."""
        if file_path.suffix.lower() != ".xls":
            return file_path
        try:
            from xls2xlsx import XLS2XLSX

            new_path = file_path.with_suffix(".xlsx")
            x2x = XLS2XLSX(str(file_path))
            x2x.to_xlsx(str(new_path))
            file_path.unlink()
            logger.debug(f"Converted {file_path.name} -> {new_path.name}")
            return new_path
        except Exception as e:
            logger.warning(f"XLS conversion error for {file_path.name}: {e}")
            return file_path

    def _mark_deprecated(self, used_resource_ids: set[int]) -> int:
        """Помечает устаревшими ресурсы, которых не было в текущем обновлении,
        и архивирует их последний файл на диске."""
        resources = Resource.objects.exclude(id__in=used_resource_ids).filter(deprecated=False)
        count = 0
        for resource in resources:
            resource.deprecated = True
            resource.save()

            last_version = (
                FileVersion.objects.filter(resource=resource)
                .order_by("-last_changed", "-timestamp")
                .first()
            )
            if last_version:
                self._archive_file(resource, last_version)

            count += 1
        return count
