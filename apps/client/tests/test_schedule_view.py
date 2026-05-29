import pytest
from django.urls import reverse

from apps.client.services import client_helpers
from apps.client.services.client_helpers import TooManyEventsFoundError, has_more_events_than
from apps.client.views import lesson_kind_class
from apps.common.models import Event


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
    assert 'aria-controls="addition-filters-container"' in content
    assert 'aria-expanded="false"' in content
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
def test_schedule_page_accessibility_landmarks(client):
    response = client.get(reverse("schedule:index"), {"date": "today"})

    assert response.status_code == 200
    content = response.content.decode()
    assert 'role="status"' in content
    assert 'aria-hidden="true"' in content
    assert "hidden" in content


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


@pytest.mark.django_db
def test_schedule_page_redirects_empty_and_default_get_params(client):
    response = client.get(
        reverse("schedule:index"),
        {
            "date": "today",
            "left_date": "",
            "right_date": "",
            "addition_filters_visible": "0",
        },
    )

    assert response.status_code == 302
    assert response.url == f"{reverse('schedule:index')}?date=today"


@pytest.mark.django_db
def test_schedule_page_keeps_visible_addition_filters_param(client):
    response = client.get(
        reverse("schedule:index"),
        {
            "date": "today",
            "left_date": "",
            "right_date": "",
            "addition_filters_visible": "1",
        },
    )

    assert response.status_code == 302
    assert response.url == f"{reverse('schedule:index')}?date=today&addition_filters_visible=1"


@pytest.mark.django_db
def test_schedule_page_shows_too_many_events_state(client, monkeypatch):
    def make_too_many_events_data(filters):
        raise TooManyEventsFoundError(250)

    monkeypatch.setattr("apps.client.views.make_table_data", make_too_many_events_data)

    response = client.get(reverse("schedule:index"), {"date": "today"}, HTTP_ACCEPT_LANGUAGE="en")

    assert response.status_code == 200
    assert response.context["too_many_events_found"] is True
    assert response.context["data"] == []
    content = response.content.decode()
    assert 'data-lucide="shield-alert"' in content
    assert "Too many classes found" in content
    assert "more than 250 classes" in content


@pytest.mark.django_db
@pytest.mark.parametrize(
    "params",
    [
        {"date": "single_date", "left_date": "not-a-date"},
        {"date": "range_date", "left_date": "2026-05-29", "right_date": "not-a-date"},
    ],
)
def test_schedule_page_handles_invalid_dates_without_server_error(client, params):
    response = client.get(reverse("schedule:index"), params)

    assert response.status_code == 200
    assert response.context["data"] == []
    assert response.context["too_many_events_found"] is False


@pytest.mark.django_db
def test_has_more_events_than_detects_limit():
    Event.objects.bulk_create(Event() for _ in range(251))

    assert has_more_events_than(Event.objects.all(), 250) is True
    assert has_more_events_than(Event.objects.all(), 251) is False


def test_filter_options_falls_back_to_process_cache_when_django_cache_fails(monkeypatch):
    class BrokenCache:
        def get(self, key):
            raise ConnectionError("cache is unavailable")

        def set(self, key, value, timeout):
            raise ConnectionError("cache is unavailable")

    options = {
        "groups": ["РџР РРќ-101"],
        "teachers": ["РџСЂРµРїРѕРґР°РІР°С‚РµР»СЊ"],
        "places": ["Рђ 101"],
        "subjects": ["РўРµСЃС‚РѕРІС‹Р№ РїСЂРµРґРјРµС‚"],
        "kinds": ["Р›РµРєС†РёСЏ"],
        "time_slots": ["8:30"],
    }
    calls = 0

    def build_filter_options():
        nonlocal calls
        calls += 1
        return options

    monkeypatch.setattr(client_helpers, "_process_filter_options_cache", None)
    monkeypatch.setattr(client_helpers, "cache", BrokenCache())
    monkeypatch.setattr(client_helpers, "_build_filter_options", build_filter_options)

    assert client_helpers.get_cached_filter_options() == options
    assert client_helpers.get_cached_filter_options() == options
    assert calls == 1


def test_filter_options_prefers_django_cache_when_process_cache_exists(monkeypatch):
    class WorkingCache:
        def get(self, key):
            return redis_options

        def set(self, key, value, timeout):
            raise AssertionError("set should not be called on cache hit")

    process_options = {
        "groups": ["process"],
        "teachers": [],
        "places": [],
        "subjects": [],
        "kinds": [],
        "time_slots": [],
    }
    redis_options = {
        "groups": ["redis"],
        "teachers": [],
        "places": [],
        "subjects": [],
        "kinds": [],
        "time_slots": [],
    }

    monkeypatch.setattr(client_helpers, "cache", WorkingCache())
    client_helpers._set_process_cached_filter_options(process_options)

    assert client_helpers.get_cached_filter_options() == redis_options


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
