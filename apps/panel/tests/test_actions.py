import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.common.models import Alert
from apps.panel.tasks import run_panel_action_task


@pytest.mark.django_db
def test_actions_panel_requires_staff_login(client):
    response = client.get(reverse("panel_actions"))

    assert response.status_code == 302
    assert "/admin/login/" in response.url


@pytest.mark.django_db
def test_actions_panel_renders_for_staff(admin_client):
    response = admin_client.get(reverse("panel_actions"))

    assert response.status_code == 200
    assert "Импорт справочника дисциплин" in response.content.decode()


@pytest.mark.django_db
def test_panel_action_endpoint_queues_uploaded_file(
    admin_client,
    monkeypatch,
    settings,
    tmp_path,
):
    settings.DATA_STORAGE_DIR = tmp_path
    settings.CELERY_TASK_ALWAYS_EAGER = False
    queued = {}

    class FakeResult:
        id = "queued-task-id"

    def fake_delay(action_id, *, upload_path="", mode=""):
        queued["action_id"] = action_id
        queued["upload_path"] = upload_path
        queued["mode"] = mode
        return FakeResult()

    monkeypatch.setattr(run_panel_action_task, "delay", fake_delay)

    response = admin_client.post(
        reverse("panel_action_run"),
        {
            "action_id": "import_subject_reference",
            "upload": SimpleUploadedFile("subjects.json", b"[]"),
        },
    )

    assert response.status_code == 202
    assert response.json() == {"status": "running", "id": "queued-task-id"}
    assert queued["action_id"] == "import_subject_reference"
    assert queued["mode"] == ""
    assert queued["upload_path"]


@pytest.mark.django_db
def test_panel_action_task_creates_admin_alert_on_failure(monkeypatch):
    def fail_action(action_id, *, upload_path="", mode=""):
        raise RuntimeError("broken action")

    monkeypatch.setattr("apps.panel.services.actions.run_panel_action", fail_action)

    with pytest.raises(RuntimeError, match="broken action"):
        run_panel_action_task.apply(args=("create_organization",), throw=True)

    alert = Alert.objects.get()
    assert alert.is_admin is True
    assert alert.is_dismissible is True
    assert alert.category == Alert.Category.DANGER
    assert "broken action" in alert.body
