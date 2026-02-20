import shutil
from datetime import datetime
from pathlib import Path

import fs
from asgiref.sync import sync_to_async
from django.core.management import call_command
from fs.googledrivefs import GoogleDriveFS
from fs.osfs import OSFS
from fs.tempfs import TempFS
from fs.copy import copy_fs
from google.oauth2 import service_account

from timetable_project.settings import STATIC_ROOT, DATA_STORAGE_DIR, GOOGLE_AUTH_FILE
from timetable.models import Task, Snapshot


def _get_timestamp() -> str:
    """
    Возвращает текущую метку времени в формате ГГГГ-ММ-ДД_ЧЧ-ММ-СС.
    """
    return datetime.now().strftime('%Y-%m-%d_%H-%M-%S')


def _create_backup_dir(subfolder_name: str) -> Path:
    """
    Создаёт (при отсутствии) и возвращает путь к директории для будущего бэкапа.
    """
    backup_dir = STATIC_ROOT / 'snapshot' / subfolder_name
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def _zip_directory(source_dir: Path, destination_path_no_ext: Path) -> Path:
    """
    Архивирует (в zip) директорию `source_dir` в архив `destination_path_no_ext + .zip`.
    Возвращает полный путь к архиву.
    """
    shutil.make_archive(str(destination_path_no_ext), 'zip', str(source_dir))
    return Path(str(destination_path_no_ext) + '.zip')


async def _dump_database(output_file: Path):
    """
    Выгружает (dump) базу данных в указанный файл `output_file`.
    """
    with output_file.open('w') as f:
        await sync_to_async(call_command)('dumpdata', stdout=f)


def _copy_google_fs_to_temp(temp_fs) -> None:
    """
    Копирует содержимое Google Drive в `temp_fs`.
    """
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = service_account.Credentials.from_service_account_file(str(GOOGLE_AUTH_FILE), scopes=SCOPES)
    google_fs = GoogleDriveFS(creds)
    copy_fs(google_fs, temp_fs)


def _copy_local_fs_to_temp(temp_fs) -> None:
    """
    Копирует локальную директорию DATA_STORAGE_DIR в `temp_fs`.
    """
    local_fs = OSFS(str(DATA_STORAGE_DIR))
    copy_fs(local_fs, temp_fs)




async def database_backup():
    """
    Создаёт бэкап базы данных и возвращает путь к полученному .json файлу.
    """
    backup_dir = _create_backup_dir('database_backups')
    now = _get_timestamp()
    backup_file = backup_dir / f'backup_{now}.json'

    await _dump_database(backup_file)
    return backup_file


def local_backup():
    """
    Создаёт бэкап локальных файлов и возвращает путь к полученному .zip архиву.
    """
    backup_dir = _create_backup_dir('local_filesystem')
    now = _get_timestamp()
    backup_file_no_ext = backup_dir / f'local_backup_{now}'
    return _zip_directory(DATA_STORAGE_DIR, backup_file_no_ext)


def google_backup():
    """
    Создаёт бэкап файлов Google Drive и возвращает путь к полученному .zip архиву.
    """
    backup_dir = _create_backup_dir('google_filesystem')
    now = _get_timestamp()
    backup_file_no_ext = backup_dir / f'google_backup_{now}'

    with TempFS() as temp_fs:
        _copy_google_fs_to_temp(temp_fs)
        archive_path = _zip_directory(Path(temp_fs.root_path), backup_file_no_ext)

    return archive_path


async def all_backup():
    """
    Создаёт бэкап всей доступной инфраструктуры (Google Drive, локальное хранилище, база данных)
    и возвращает путь к полученному .zip архиву.
    """
    backup_dir = _create_backup_dir('full_backup')
    now = _get_timestamp()
    backup_file_no_ext = backup_dir / f'all_components_backup_{now}'

    with TempFS() as temp_fs:
        # Копируем Google Drive
        temp_fs.makedir('google')
        _copy_google_fs_to_temp(temp_fs.opendir('google'))

        # Копируем локальное хранилище
        temp_fs.makedir('local')
        _copy_local_fs_to_temp(temp_fs.opendir('local'))

        # Сохраняем бэкап базы
        db_file = Path(temp_fs.root_path) / 'database_dump.json'
        await _dump_database(db_file)

        archive_path = _zip_directory(Path(temp_fs.root_path), backup_file_no_ext)

    return archive_path


async def task_make_snapshot(task: Task):
    try:
        type = task.params.get('snapshot', None)
        match (type):
            case 'База данных':
                file_path = await database_backup()
            case 'Локальное хранилище':
                file_path = local_backup()
            case 'Google Drive':
                file_path = google_backup()
            case 'Вся система':
                file_path = await all_backup()
            case _:
                return

        url = str(file_path.relative_to(STATIC_ROOT))
        await sync_to_async(Snapshot.objects.create)(type=type, path=url)
        result = {
            'url': url,
        }
        task.result = result
        task.status = 'success'
    except Exception as e:
        task.status = 'error'
        task.result = {'error': str(e)}
    await sync_to_async(task.save)()