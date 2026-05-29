import pytest
from django.urls import reverse

from apps.client.views import lesson_kind_class


@pytest.mark.django_db
def test_schedule_page_renders(client):
    response = client.get(reverse("schedule:index"))

    assert response.status_code == 200
    content = response.content.decode()
    assert '<html lang="ru">' in content
    assert "Расписание занятий ВолгГТУ" in content
    assert 'method="get"' in content
    assert 'name="group"' in content
    assert 'name="group[]"' not in content
    assert "jquery" not in content.lower()
    assert "select2" not in content.lower()


@pytest.mark.django_db
def test_schedule_page_renders_english(client):
    response = client.get(reverse("schedule:index"), HTTP_ACCEPT_LANGUAGE="en")

    assert response.status_code == 200
    content = response.content.decode()
    assert '<html lang="en">' in content
    assert "VSTU Class Schedule" in content
    assert "Schedule filters" in content
    assert 'data-autocomplete-placeholder="Start typing"' in content
    assert 'data-remove-label-template="Remove __value__"' in content


@pytest.mark.django_db
def test_schedule_post_does_not_redirect_to_get(client):
    response = client.post(
        reverse("schedule:index"),
        {
            "date": "tomorrow",
            "group": ["ПРИН-101"],
            "csrfmiddlewaretoken": "token",
        },
    )

    assert response.status_code == 200
    assert "Location" not in response


@pytest.mark.parametrize(
    ("kind", "css_class"),
    [
        ("Лекция", "chip-kind--lecture"),
        ("лекция", "chip-kind--lecture"),
        ("Практика", "chip-kind--practice"),
        ("пр. занятие", "chip-kind--practice"),
        ("Лабораторная работа", "chip-kind--lab"),
    ],
)
def test_lesson_kind_class(kind, css_class):
    assert lesson_kind_class(kind) == css_class
