import json

import pytest
from django.template.loader import render_to_string
from django.test import override_settings
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
    assert '<meta name="theme-color" content="#0876cf">' in content
    assert '<link rel="apple-touch-icon" href="/static/pwa/icon-180.png">' in content
    assert '<link rel="manifest" href="/manifest.ru.webmanifest">' in content
    assert 'navigator.serviceWorker.register("/sw.js")' in content
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
    assert '<link rel="manifest" href="/manifest.en.webmanifest">' in content
    assert 'data-autocomplete-placeholder="Start typing"' in content
    assert 'data-remove-label-template="Remove __value__"' in content


def test_export_dropdown_is_a_reusable_mode_component():
    content = render_to_string(
        "timetable/components/export_dropdown.html",
        {"export_query": "date=range_date&left_date=2026-02-01&group=TEST-101"},
    )

    assert 'data-export-url="/api/export/"' in content
    assert (
        'data-export-query="date=range_date&amp;left_date=2026-02-01&amp;group=TEST-101"' in content
    )
    assert 'value="events"' in content
    assert 'value="schedule"' in content
    assert 'data-export-format="csv"' in content
    assert 'data-export-format="ics"' in content
    assert 'data-export-format="json"' in content
    assert "Занятия — конкретные события за выбранный период" in content
    assert "Расписание — повторяющийся план активных расписаний" in content


def _streaming_text(response) -> str:
    return b"".join(response.streaming_content).decode()


@pytest.mark.parametrize(
    ("url", "name", "short_name"),
    [
        ("/manifest.ru.webmanifest", "Расписание занятий ВолгГТУ", "Расписание"),
        ("/manifest.en.webmanifest", "VSTU Class Schedule", "Schedule"),
    ],
)
def test_pwa_manifest_endpoint(client, url, name, short_name):
    response = client.get(url)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/manifest+json")
    manifest = json.loads(_streaming_text(response))
    assert manifest["name"] == name
    assert manifest["short_name"] == short_name
    assert manifest["start_url"] == "/schedule/"
    assert manifest["scope"] == "/schedule/"
    assert manifest["theme_color"] == "#0876cf"
    assert manifest["background_color"] == "#f5f7fa"
    assert {icon["sizes"] for icon in manifest["icons"]} == {"192x192", "512x512"}
    assert all(icon["purpose"] == "any maskable" for icon in manifest["icons"])


def test_pwa_service_worker_endpoint(client):
    response = client.get("/sw.js")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/javascript")
    assert response["Service-Worker-Allowed"] == "/"
    content = _streaming_text(response)
    assert 'self.addEventListener("install"' in content
    assert "self.skipWaiting()" in content
    assert 'self.addEventListener("activate"' in content
    assert "self.clients.claim()" in content


@pytest.mark.django_db
def test_schedule_page_accessibility_landmarks(client):
    response = client.get(reverse("schedule:index"), {"date": "today"})

    assert response.status_code == 200
    content = response.content.decode()
    assert 'role="status"' in content
    assert 'aria-hidden="true"' in content
    assert "hidden" in content


@override_settings(DEBUG=False)
def test_client_404_renders_schedule_error_page(client):
    response = client.get("/missing-page/", HTTP_ACCEPT_LANGUAGE="en")

    assert response.status_code == 404
    content = response.content.decode()
    assert "Page not found" in content
    assert "Return to the home page" in content
    assert "Schedule filters" not in content


@override_settings(DEBUG=False)
def test_api_404_keeps_json_error_response(client):
    response = client.get("/api/missing/", HTTP_ACCEPT="application/json")

    assert response.status_code == 404
    assert response["Content-Type"].startswith("application/json")


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
        "teachers": ["Process teacher"],
        "places": ["P 101"],
        "subjects": ["Process subject"],
        "kinds": ["Practice"],
        "time_slots": ["10:10"],
    }
    redis_options = {
        "groups": ["redis"],
        "teachers": ["Redis teacher"],
        "places": ["R 101"],
        "subjects": ["Redis subject"],
        "kinds": ["Lecture"],
        "time_slots": ["08:30"],
    }

    monkeypatch.setattr(client_helpers, "cache", WorkingCache())
    client_helpers._set_process_cached_filter_options(process_options)

    assert client_helpers.get_cached_filter_options() == redis_options


def test_filter_options_with_empty_reference_are_not_cached(monkeypatch):
    class WorkingCache:
        def get(self, key):
            return None

        def set(self, key, value, timeout):
            raise AssertionError("empty filter options must not be cached")

    options = {
        "groups": [],
        "teachers": ["Teacher"],
        "places": ["A 101"],
        "subjects": ["Subject"],
        "kinds": ["Lecture"],
        "time_slots": ["08:30"],
    }
    monkeypatch.setattr(client_helpers, "cache", WorkingCache())
    monkeypatch.setattr(client_helpers, "_build_filter_options", lambda: options)

    assert client_helpers.get_cached_filter_options() == options


def test_filter_options_discards_cached_empty_reference(monkeypatch):
    class WorkingCache:
        def __init__(self):
            self.deleted_keys = []

        def get(self, key):
            return cached_options

        def delete(self, key):
            self.deleted_keys.append(key)

        def set(self, key, value, timeout):
            raise AssertionError("empty filter options must not be cached")

    cached_options = {
        "groups": [],
        "teachers": ["Teacher"],
        "places": ["A 101"],
        "subjects": ["Subject"],
        "kinds": ["Lecture"],
        "time_slots": ["08:30"],
    }
    cache = WorkingCache()
    monkeypatch.setattr(client_helpers, "cache", cache)
    monkeypatch.setattr(client_helpers, "_build_filter_options", lambda: cached_options)

    assert client_helpers.get_cached_filter_options() == cached_options
    assert cache.deleted_keys == [client_helpers.FILTER_OPTIONS_CACHE_KEY]


def test_invalidate_cached_filter_options_clears_shared_and_process_caches(monkeypatch):
    class WorkingCache:
        def __init__(self):
            self.deleted_keys = []

        def delete(self, key):
            self.deleted_keys.append(key)

    cache = WorkingCache()
    monkeypatch.setattr(client_helpers, "cache", cache)
    client_helpers._set_process_cached_filter_options({"groups": ["group"]})

    client_helpers.invalidate_cached_filter_options()

    assert client_helpers._process_filter_options_cache is None
    assert cache.deleted_keys == [client_helpers.FILTER_OPTIONS_CACHE_KEY]


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
