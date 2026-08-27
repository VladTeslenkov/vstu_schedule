from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.panel.models import CeleryTaskConfig, CeleryTaskRun
from apps.panel.views import task_view

TASK_NAME = "panel.tasks.update_timetable"


@pytest.fixture
def running_run(db):
    CeleryTaskConfig.objects.get_or_create(task_name=TASK_NAME)
    return CeleryTaskRun.objects.create(
        task_id="running-task-id",
        task_name=TASK_NAME,
        status=CeleryTaskRun.Status.STARTED,
        started_at=timezone.now(),
    )


@pytest.mark.django_db
def test_running_task_is_shown_even_after_a_skipped_run(admin_client, monkeypatch, running_run):
    monkeypatch.setattr(task_view, "active_celery_task_ids", lambda: {running_run.task_id})
    CeleryTaskRun.objects.create(
        task_id="skipped-task-id",
        task_name=TASK_NAME,
        status=CeleryTaskRun.Status.SKIPPED,
        started_at=timezone.now(),
        finished_at=timezone.now(),
        result_text="Task skipped by concurrency policy.",
    )

    response = admin_client.get(reverse("panel_tasks"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "выполняется" in content
    assert f'value="{running_run.id}"' in content


@pytest.mark.django_db
def test_run_without_concurrency_lock_is_reported_as_stale(admin_client, monkeypatch, running_run):
    monkeypatch.setattr(task_view, "active_celery_task_ids", set)
    running_run.started_at = timezone.now() - timedelta(hours=1)
    running_run.save(update_fields=["started_at"])

    response = admin_client.get(reverse("panel_tasks"))

    assert response.status_code == 200
    assert "нет ответа воркера" in response.content.decode()


@pytest.mark.django_db
def test_task_log_page_marks_the_running_run(admin_client, monkeypatch, running_run):
    monkeypatch.setattr(task_view, "active_celery_task_ids", lambda: {running_run.task_id})

    response = admin_client.get(reverse("panel_task_log", kwargs={"task_name": TASK_NAME}))

    assert response.status_code == 200
    assert "· выполняется" in response.content.decode()
