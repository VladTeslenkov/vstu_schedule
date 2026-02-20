from pathlib import Path

from django.apps import AppConfig

TAG_CATEGORY_MAP = {
    "education_form": "Выбрать форму обучения",
    "faculty": "Выбрать факультет",
    "course": "Выбрать курс",
}
GOOGLE_DRIVE_STORAGE_MAME = "google drive"
LOCAL_STORAGE_NAME = "local"
AVAILABLE_KEYS = {"time_update", "analyze_url", "google_json_dir", "download_storage"}
from django.apps import AppConfig


class TimetableConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "timetable"

    def ready(self):
        from timetable.cron_utils import create_update_timetable_cron_task

        create_update_timetable_cron_task()
