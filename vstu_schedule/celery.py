import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vstu_schedule.settings")

app = Celery('vstu_schedule_background')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
