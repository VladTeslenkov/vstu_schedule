from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone, translation

from apps.common.models import Alert
from apps.common.selectors import admin_alerts, public_alerts


@pytest.mark.django_db
def test_public_alerts_include_only_active_non_admin_alerts():
    Alert.objects.create(title="Public", body="Visible")
    Alert.objects.create(title="Admin", body="Hidden", is_admin=True)
    Alert.objects.create(title="Disabled", body="Hidden", is_enabled=False)
    Alert.objects.create(
        title="Expired",
        body="Hidden",
        expires_at=timezone.now() - timedelta(minutes=1),
    )

    assert list(public_alerts().values_list("title", flat=True)) == ["Public"]


@pytest.mark.django_db
def test_admin_alerts_include_active_admin_alerts():
    visible = Alert.objects.create(title="Visible", body="Body", is_admin=True)
    Alert.objects.create(title="Public", body="Body")
    Alert.objects.create(title="Disabled", body="Body", is_admin=True, is_enabled=False)

    assert list(admin_alerts()) == [visible]


@pytest.mark.django_db
def test_dismiss_admin_alert_deletes_dismissible_alert(admin_client):
    alert = Alert.objects.create(title="Visible", body="Body", is_admin=True, is_dismissible=True)

    response = admin_client.post(reverse("dismiss_admin_alert", args=[alert.pk]))

    assert response.status_code == 200
    assert response.json() == {"ok": True, "deleted": True}
    assert not Alert.objects.filter(pk=alert.pk).exists()


@pytest.mark.django_db
def test_dismiss_admin_alert_keeps_non_dismissible_alert(admin_client):
    alert = Alert.objects.create(title="Visible", body="Body", is_admin=True, is_dismissible=False)

    response = admin_client.post(reverse("dismiss_admin_alert", args=[alert.pk]))

    assert response.status_code == 200
    assert response.json() == {"ok": True, "deleted": False}
    assert Alert.objects.filter(pk=alert.pk).exists()


@pytest.mark.django_db
def test_schedule_page_renders_localized_alert(client):
    Alert.objects.create(
        title="Ru title",
        body="Ru body",
        title_en="English title",
        body_en="English body",
    )

    with translation.override("en"):
        response = client.get(reverse("schedule:index"), HTTP_ACCEPT_LANGUAGE="en")

    content = response.content.decode()
    assert response.status_code == 200
    assert "English title" in content
    assert "English body" in content
    assert "Ru title" not in content
