from datetime import date, time
from http import HTTPStatus

import pytest
from django.urls import reverse

from apps.api.models import ApiClient
from apps.common.models import (
    AbstractDay,
    AbstractEvent,
    Department,
    Event,
    EventKind,
    EventParticipant,
    EventPlace,
    Organization,
    Schedule,
    ScheduleMetadata,
    ScheduleTemplate,
    ScheduleTemplateMetadata,
    Subject,
    TimeSlot,
)


@pytest.mark.django_db
def test_reference_endpoint_returns_public_contract(client):
    _create_event()

    response = client.get(reverse("api:reference"))

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert set(payload) == {"groups", "teachers", "disciplines", "places"}
    assert payload["groups"][0]["name"] == "TEST-101"
    assert payload["disciplines"][0]["name"] == "Test discipline"


@pytest.mark.django_db
def test_export_json_returns_visualization_query(client):
    _create_event()

    response = client.get(reverse("api:export"), {"date": "single_date", "left_date": "2026-02-02"})

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["count"] == 1
    assert payload["filters"] == {
        "date": "single_date",
        "left_date": "2026-02-02",
        "right_date": "",
        "group": [],
        "teacher": [],
        "place": [],
        "subject": [],
        "kind": [],
        "time_slot": [],
    }
    assert payload["events"][0]["subject"]["name"] == "Test discipline"


@pytest.mark.django_db
def test_export_csv(client):
    _create_event()

    response = client.get(
        reverse("api:export"),
        {"date": "single_date", "left_date": "2026-02-02", "format": "csv"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response["Content-Type"].startswith("text/csv")
    assert "Content-Disposition" not in response
    assert response["X-Export-Filename"] == "schedule_2026-02-02.csv"
    assert "Test discipline" in response.content.decode("utf-8-sig")


@pytest.mark.django_db
def test_export_filename_includes_selected_reference_filters(client):
    _create_event()

    response = client.get(
        reverse("api:export"),
        {
            "date": "single_date",
            "left_date": "2026-02-02",
            "group": "TEST-101",
            "teacher": "Teacher Example",
            "place": "B 101",
            "format": "json",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert (
        response["X-Export-Filename"]
        == "schedule_groups_TEST-101_teachers_Teacher-Example_rooms_B-101_2026-02-02.json"
    )


@pytest.mark.django_db
def test_export_filename_prefers_selected_reference_filters(client):
    _create_event()

    response = client.get(
        reverse("api:export"),
        {"group": "TEST-101", "format": "json"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response["X-Export-Filename"] == "schedule_groups_TEST-101.json"


@pytest.mark.django_db
def test_export_works_with_browser_accept_header(client):
    _create_event()

    response = client.get(
        reverse("api:export"),
        {"date": "single_date", "left_date": "2026-02-02", "format": "json"},
        HTTP_ACCEPT="text/html,application/xhtml+xml",
    )

    assert response.status_code == HTTPStatus.OK
    assert response["Content-Type"].startswith("application/json")


@pytest.mark.django_db
def test_model_endpoint_requires_auth(client):
    response = client.get(reverse("api:event"))

    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.django_db
def test_token_allows_model_endpoint(client):
    _create_event()
    api_client, secret = ApiClient.create_with_secret(name="Test client")

    token_response = client.post(
        reverse("api:token"),
        data={"client_id": api_client.client_id, "client_secret": secret},
        content_type="application/json",
    )

    assert token_response.status_code == HTTPStatus.OK
    token = token_response.json()["access_token"]
    response = client.get(
        reverse("api:event"),
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()[0]["fields"]["subject_override_id"] is not None


@pytest.mark.django_db
def test_swagger_requires_staff_login(client):
    response = client.get(reverse("api:docs"))

    assert response.status_code == HTTPStatus.FOUND


def _create_event() -> Event:
    org = Organization.objects.create(name="Test university")
    department = Department.objects.create(
        name="Test department",
        shortname="TD",
        code="TD",
        organization=org,
    )
    template_metadata = ScheduleTemplateMetadata.objects.create(
        faculty="TD",
        scope=ScheduleTemplateMetadata.Scope.BACHELOR,
    )
    template = ScheduleTemplate.objects.create(
        metadata=template_metadata,
        repetition_period=7,
        repeatable=True,
        aligned_by_week_day=1,
        department=department,
    )
    metadata = ScheduleMetadata.objects.create(years="2025-2026", course=1, semester=2)
    day = AbstractDay.objects.create(day_number=0, name="Monday")
    schedule = Schedule.objects.create(
        metadata=metadata,
        status=Schedule.Status.ACTIVE,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 6, 1),
        starting_day_number=day,
        schedule_template=template,
    )
    kind = EventKind.objects.create(name="Lecture")
    subject = Subject.objects.create(name="Test discipline")
    time_slot = TimeSlot.objects.create(
        alt_name="1-2",
        start_time=time(8, 30),
        end_time=time(10, 0),
    )
    group = EventParticipant.objects.create(
        name="TEST-101",
        role=EventParticipant.Role.STUDENT,
        is_group=True,
        department=department,
    )
    teacher = EventParticipant.objects.create(
        name="Teacher Example",
        role=EventParticipant.Role.TEACHER,
        is_group=False,
        department=department,
    )
    place = EventPlace.objects.create(building="B", room="101")
    abstract_event = AbstractEvent.objects.create(
        kind=kind,
        subject=subject,
        abstract_day=day,
        time_slot=time_slot,
        schedule=schedule,
    )
    event = Event.objects.create(
        date=date(2026, 2, 2),
        kind_override=kind,
        subject_override=subject,
        time_slot_override=time_slot,
        abstract_event=abstract_event,
    )
    event.participants_override.set([group, teacher])
    event.places_override.set([place])
    return event
