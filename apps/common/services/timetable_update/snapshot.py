import logging
import shutil
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command

logger = logging.getLogger(__name__)


def _get_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _create_backup_dir(subfolder_name: str) -> Path:
    backup_dir = Path(settings.STATIC_ROOT) / "snapshot" / subfolder_name
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def _zip_directory(source_dir: Path, destination_no_ext: Path) -> Path:
    shutil.make_archive(str(destination_no_ext), "zip", str(source_dir))
    return Path(str(destination_no_ext) + ".zip")


def database_backup() -> Path:
    """Создаёт дамп БД в JSON и возвращает путь к файлу."""
    backup_dir = _create_backup_dir("database_backups")
    backup_file = backup_dir / f"backup_{_get_timestamp()}.json"
    with backup_file.open("w", encoding="utf-8") as f:
        call_command("dumpdata", stdout=f)
    logger.info(f"Database backup created: {backup_file}")
    return backup_file


def local_backup() -> Path:
    """Создаёт zip-архив локального хранилища и возвращает путь к архиву."""
    backup_dir = _create_backup_dir("local_filesystem")
    backup_file_no_ext = backup_dir / f"local_backup_{_get_timestamp()}"
    archive = _zip_directory(settings.DATA_STORAGE_DIR, backup_file_no_ext)
    logger.info(f"Local backup created: {archive}")
    return archive


def full_backup() -> Path:
    """Создаёт общий zip-архив (БД + локальные файлы)."""
    backup_dir = _create_backup_dir("full_backup")
    now = _get_timestamp()

    # Временная папка для сборки
    temp_dir = backup_dir / f"temp_{now}"
    temp_dir.mkdir()

    try:
        # БД
        db_file = temp_dir / "database_dump.json"
        with db_file.open("w", encoding="utf-8") as f:
            call_command("dumpdata", stdout=f)

        # Локальные файлы
        local_dest = temp_dir / "local"
        shutil.copytree(settings.DATA_STORAGE_DIR, local_dest)

        archive = _zip_directory(temp_dir, backup_dir / f"full_backup_{now}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    logger.info(f"Full backup created: {archive}")
    return archive


def make_snapshot(snapshot_type: str) -> str:
    """
    Создаёт снимок системы по типу и возвращает относительный путь к файлу.
    Вызывается из Celery-задачи.

    :param snapshot_type: "База данных", "Локальное хранилище", "Вся система"
    """
    match snapshot_type:
        case "База данных":
            file_path = database_backup()
        case "Локальное хранилище":
            file_path = local_backup()
        case "Вся система":
            file_path = full_backup()
        case _:
            raise ValueError(f"Неизвестный тип снимка: {snapshot_type!r}")

    return str(file_path.relative_to(settings.STATIC_ROOT))