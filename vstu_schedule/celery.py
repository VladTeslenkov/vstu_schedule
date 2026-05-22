import os

from celery import Celery
from celery.signals import beat_init, worker_ready

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vstu_schedule.settings")

app = Celery("vstu_schedule_background")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@worker_ready.connect
@beat_init.connect
def validate_task_descriptors(**kwargs):
    from apps.common.services.celery_task_descriptors import (
        warn_about_missing_task_descriptors,
    )

    warn_about_missing_task_descriptors()
