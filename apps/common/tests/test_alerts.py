from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone, translation

from apps.common.models import Alert
from apps.common.selectors import admin_alerts, public_alerts
from apps.common.services.alerts import render_alert_body


def test_render_alert_body_supports_approved_inline_markdown():
    rendered = render_alert_body(
        "**Strong** and *emphasis* and `code` and [safe link](https://example.com)\nnext line"
    )

    assert "<strong>Strong</strong>" in rendered
    assert "<em>emphasis</em>" in rendered
    assert "<code>code</code>" in rendered
    assert '<a href="https://example.com">safe link</a>' in rendered
    assert "<br" in rendered
    assert "next line" in rendered


def test_render_alert_body_escapes_html_and_rejects_unsafe_links_and_images():
    rendered = render_alert_body(
        '<script>alert("xss")</script> '
        "[unsafe](javascript:alert(1)) "
        "![tracking](https://example.com/pixel.png)"
    )

    assert "<script" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "<img" not in rendered
    assert 'href="javascript:' not in rendered


def test_render_alert_body_does_not_create_block_markup():
    rendered = render_alert_body("# Heading\n- list item\n> quotation")

    assert "<h1" not in rendered
    assert "<ul" not in rendered
    assert "<blockquote" not in rendered
    assert "# Heading" in rendered
    assert "- list item" in rendered
    assert "&gt; quotation" in rendered


@pytest.mark.django_db
def test_public_alerts_include_only_active_non_admin_alerts():
    Alert.objects.all().delete()

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
def test_admin_alerts_feed_returns_active_admin_alerts(admin_client):
    visible = Alert.objects.create(
        title="Visible",
        body="**Formatted body**",
        is_admin=True,
        is_dismissible=True,
    )
    Alert.objects.create(title="Public", body="Body")
    Alert.objects.create(title="Disabled", body="Body", is_admin=True, is_enabled=False)

    response = admin_client.get(reverse("admin_alerts_feed"))

    assert response.status_code == 200
    assert response.json() == {
        "alerts": [
            {
                "id": visible.pk,
                "category": visible.category,
                "icon_name": visible.icon_name,
                "title": visible.display_title,
                "body": visible.display_body,
                "body_html": render_alert_body(visible.display_body),
                "is_dismissible": True,
                "dismiss_url": reverse("dismiss_admin_alert", args=[visible.pk]),
            }
        ]
    }


@pytest.mark.django_db
def test_admin_alerts_feed_requires_staff_login(client):
    response = client.get(reverse("admin_alerts_feed"))

    assert response.status_code == 302
    assert "/admin/login/" in response.url


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
def test_schedule_page_renders_localized_alert_body_markdown(client):
    Alert.objects.create(
        title="Ru title",
        body="**Ru strong**",
        title_en="English title",
        body_en='[English link](https://example.com) <script>alert("x")</script>',
    )

    with translation.override("en"):
        response = client.get(reverse("schedule:index"), HTTP_ACCEPT_LANGUAGE="en")

    content = response.content.decode()
    assert response.status_code == 200
    assert '<a href="https://example.com">English link</a>' in content
    assert "&lt;script&gt;" in content
    assert "<script>alert" not in content
    assert "Ru strong" not in content


@pytest.mark.django_db
def test_panel_page_renders_alert_body_markdown(admin_client):
    Alert.objects.create(
        title="Plain **title**",
        body="**Formatted body**",
        is_admin=True,
    )

    response = admin_client.get(reverse("monitoring_panel"))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Plain **title**" in content
    assert "<strong>Formatted body</strong>" in content
