from datetime import date, time

import pytest

from apps.api.services.filters import filters_from_query
from apps.api.services.serialization import serialize_event
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
def test_serialize_event_contract_shape():
    event = _create_event()

    serialized = serialize_event(event)

    assert serialized.id == event.pk
    assert serialized.date == date(2026, 2, 2)
    assert serialized.subject is not None
    assert serialized.kind is not None
    assert serialized.schedule is not None
    assert serialized.subject.name == "Test discipline"
    assert serialized.kind.name == "Lecture"
    assert serialized.groups[0].name == "TEST-101"
    assert serialized.teachers[0].name == "Teacher Example"
    assert serialized.places[0].display_name == "B 101"
    assert serialized.schedule.course == 1


def test_filters_from_query_accepts_list_syntax():
    filters = filters_from_query(
        {
            "date": "range_date",
            "left_date": "2026-02-01",
            "right_date": "2026-02-07",
            "group": ["TEST-101"],
        }
    )

    assert filters["date"] == "range_date"
    assert filters["group"] == ["TEST-101"]
    assert filters["teacher"] == []


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
