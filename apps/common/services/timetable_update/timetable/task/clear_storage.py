from datetime import datetime

import fs
from asgiref.sync import sync_to_async

from timetable_project.settings import DATA_STORAGE_DIR, GOOGLE_AUTH_FILE
from timetable.apps import LOCAL_STORAGE_NAME, GOOGLE_DRIVE_STORAGE_MAME
from timetable.management.commands.version_core.file_data import FileData
from timetable.management.commands.version_core.storage_manager import StorageManager
from timetable.management.commands.version_core.storage_manager_google_drive import (
    StorageManagerGoogleDrive,
)
from timetable.models import Storage, FileVersion, Resource, Tag, Task


def task_clear(task: Task):
    try:
        type = task.params.get("component", None)
        match (type):
            case "Вся система":
                clear_system()
            case "Все хранилища":
                clear_all_storages()
            case "Google Drive":
                clear_google()
            case "Локальное хранилище":
                clear_local()
            case _:
                return

        result = {
            "finished": str(datetime.now()),
        }
        task.result = result
        task.status = "success"
    except Exception as e:
        task.status = "error"
        task.result = {"error": str(e)}
    task.save()


def clear_system():
    clear_all_storages()
    Tag.objects.all().delete()
    Resource.objects.all().delete()
    FileVersion.objects.all().delete()
    Storage.objects.all().delete()
    Task.objects.all().delete()


def clear_all_storages():
    clear_local()
    clear_google()


def clear_local():
    local_fs = fs.open_fs(str(DATA_STORAGE_DIR))
    sm_local = StorageManager(LOCAL_STORAGE_NAME, local_fs)
    sm_local.clear_storage()
    clear_fileversion_and_resource()


def clear_google():
    sm_google = StorageManagerGoogleDrive(GOOGLE_DRIVE_STORAGE_MAME, GOOGLE_AUTH_FILE)
    sm_google.clear_storage()
    clear_fileversion_and_resource()


def clear_fileversion_and_resource():
    fileversions = FileVersion.objects.all()
    for fileversion in fileversions:
        storages = Storage.objects.filter(file_version=fileversion)
        if len(storages) == 0:
            fileversion.delete()

    resources = Resource.objects.all()
    for resource in resources:
        fileversions = FileVersion.objects.filter(resource=resource)
        if len(fileversions) == 0:
            resource.delete()
