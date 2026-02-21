import hashlib
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from django.conf import settings

from apps.common.models import Resource, FileVersion, Setting
from .parser import WebParser
from .file_data import FileData

logger = logging.getLogger(__name__)


class FileManager:
    """
    Управляет процессом обновления расписания:
    скачивает файлы с сайта, сравнивает хэши с предыдущими версиями,
    сохраняет новые файлы локально и создаёт записи в БД.
    """

    TIMETABLE_START_PATH = ["Расписания/Расписание занятий/"]

    def __init__(self) -> None:
        self._temp_dir: Path = settings.TEMP_DIR
        self._storage_dir: Path = settings.DATA_STORAGE_DIR
        os.environ["TMPDIR"] = str(self._temp_dir)

        try:
            self._timetable_links: list[str] = (
                Setting.objects.get(key="analyze_url").value.split(";")
            )
            logger.info(f"Loaded timetable links: {self._timetable_links}")
        except Setting.DoesNotExist:
            self._timetable_links = ["https://www.vstu.ru/student/raspisaniya/zanyatiy/"]
            logger.warning("Setting 'analyze_url' not found, using default")

    def update_timetable(self) -> None:
        """
        Основной метод: обходит все ссылки, скачивает файлы,
        проверяет изменения по хэшу и сохраняет новые версии.
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
                    file_path = self._convert_xls_to_xlsx(file_path)
                except Exception as e:
                    logger.error(f"Failed to download/convert file: {e}", exc_info=True)
                    continue

                resource_type = "Занятия" if ind == 0 else "Экзамены"

                try:
                    resource, file_version = self._process_file(file_data, file_path, resource_type)
                    if resource:
                        used_resource_ids.add(resource.id)
                except Exception as e:
                    logger.error(f"Failed to process file {file_data.get_name()}: {e}", exc_info=True)
                finally:
                    if file_path.is_file():
                        file_path.unlink()

        deprecated_count = self._mark_deprecated(used_resource_ids)
        if deprecated_count:
            logger.info(f"Marked {deprecated_count} resources as deprecated")

        logger.info("Timetable update completed")

    # ------------------- ПРИВАТНЫЕ МЕТОДЫ ------------------- #

    def _process_file(
        self, file_data: FileData, file_path: Path, resource_type: str
    ) -> tuple[Resource | None, FileVersion | None]:
        """
        Обрабатывает скачанный файл:
        - получает или создаёт Resource
        - сравнивает хэш с последней версией
        - если файл изменился — сохраняет его локально и создаёт FileVersion
        """
        resource = self._get_or_create_resource(file_data, resource_type)
        new_version = file_data.get_file_version(file_path)

        last_version = (
            FileVersion.objects.filter(resource=resource)
            .order_by("-timestamp")
            .first()
        )

        if last_version is not None and last_version.hashsum == new_version.hashsum:
            logger.info(f"No changes detected for: {resource.name}")
            return resource, None

        logger.info(f"New version detected for: {resource.name}, saving file")
        self._save_file_locally(file_path, resource)

        new_version.resource = resource
        new_version.save()
        logger.info(f"FileVersion created: id={new_version.id}")

        return resource, new_version

    def _get_or_create_resource(self, file_data: FileData, resource_type: str) -> Resource:
        """
        Ищет существующий Resource по пути или создаёт новый.
        Снимает флаг deprecated если ресурс был помечен устаревшим.
        """
        correct_path = file_data.get_correct_path()
        resource = Resource.objects.filter(path=correct_path).first()

        if resource is None:
            resource = file_data.get_resource(resource_type)
            resource.save()
            logger.debug(f"Created new resource: {resource.name}")
        elif resource.deprecated:
            resource.deprecated = False
            resource.save()

        return resource

    def _save_file_locally(self, file_path: Path, resource: Resource) -> Path:
        """
        Сохраняет файл в DATA_STORAGE_DIR по пути ресурса.
        Возвращает итоговый путь к сохранённому файлу.
        """
        dest_dir = self._storage_dir / (resource.path or resource.name)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / file_path.name
        shutil.copy2(file_path, dest_file)
        logger.debug(f"File saved to: {dest_file}")
        return dest_file

    @staticmethod
    def _convert_xls_to_xlsx(file_path: Path) -> Path:
        """Конвертирует .xls в .xlsx через LibreOffice. Если не получилось — возвращает исходный файл."""
        if file_path.suffix.lower() != ".xls":
            return file_path
        try:
            import subprocess
            result = subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "xlsx",
                 str(file_path), "--outdir", str(file_path.parent)],
                capture_output=True, timeout=60,
            )
            if result.returncode == 0:
                new_path = file_path.with_suffix(".xlsx")
                file_path.unlink()
                logger.debug(f"Converted {file_path.name} -> {new_path.name}")
                return new_path
            else:
                logger.warning(f"LibreOffice conversion failed: {result.stderr.decode()}")
        except Exception as e:
            logger.warning(f"XLS conversion error: {e}")
        return file_path

    @staticmethod
    def _mark_deprecated(used_resource_ids: set[int]) -> int:
        """Помечает устаревшими ресурсы, которых не было в текущем обновлении."""
        resources = Resource.objects.exclude(id__in=used_resource_ids).filter(deprecated=False)
        count = 0
        for resource in resources:
            resource.deprecated = True
            resource.save()
            count += 1
        return count
