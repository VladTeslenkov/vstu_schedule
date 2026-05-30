from django.db.models import QuerySet

from apps.api.schemas import (
    ApiDepartment,
    ApiEvent,
    ApiEventKind,
    ApiParticipant,
    ApiPlace,
    ApiReference,
    ApiScheduleMetadata,
    ApiSubject,
    ApiTimeSlot,
)
from apps.common.models import (
    Department,
    Event,
    EventKind,
    EventParticipant,
    EventPlace,
    Schedule,
    Subject,
    TimeSlot,
)
from apps.common.services.timetable.utilities.model_helpers import (
    get_all_groups,
    get_all_places,
    get_all_subjects,
    get_all_teachers,
)


def serialize_reference() -> ApiReference:
    return ApiReference(
        groups=serialize_participants(get_all_groups().select_related("department")),
        teachers=serialize_participants(get_all_teachers().select_related("department")),
        disciplines=serialize_subjects(get_all_subjects().order_by("name")),
        places=serialize_places(get_all_places().order_by("building", "room")),
    )


def serialize_events(events: QuerySet[Event] | list[Event]) -> list[ApiEvent]:
    return [serialize_event(event) for event in events]


def serialize_event(event: Event) -> ApiEvent:
    participants = list(event.participants_override.all())
    groups = [participant for participant in participants if participant.is_group]
    teachers = [
        participant
        for participant in participants
        if participant.role in (EventParticipant.Role.TEACHER, EventParticipant.Role.ASSISTANT)
    ]
    abstract_event = event.abstract_event
    schedule = abstract_event.schedule if abstract_event else None
    return ApiEvent(
        id=event.pk,
        date=event.date,
        abstract_event_id=abstract_event.pk if abstract_event else None,
        subject=serialize_subject(event.subject_override) if event.subject_override else None,
        kind=serialize_kind(event.kind_override) if event.kind_override else None,
        time_slot=serialize_time_slot(event.time_slot_override)
        if event.time_slot_override
        else None,
        groups=serialize_participants(groups),
        teachers=serialize_participants(teachers),
        places=serialize_places(list(event.places_override.all())),
        is_canceled=event.is_event_canceled,
        is_overridden=event.is_event_overriden,
        schedule=serialize_schedule(schedule) if schedule else None,
    )


def serialize_participants(
    participants: QuerySet[EventParticipant] | list[EventParticipant],
) -> list[ApiParticipant]:
    return [serialize_participant(participant) for participant in participants]


def serialize_participant(participant: EventParticipant) -> ApiParticipant:
    return ApiParticipant(
        id=participant.pk,
        name=participant.name,
        role=participant.role,
        is_group=participant.is_group,
        department=serialize_department(participant.department) if participant.department else None,
    )


def serialize_places(places: QuerySet[EventPlace] | list[EventPlace]) -> list[ApiPlace]:
    return [serialize_place(place) for place in places]


def serialize_place(place: EventPlace) -> ApiPlace:
    return ApiPlace(
        id=place.pk,
        building=place.building,
        room=place.room,
        display_name=str(place).strip(),
    )


def serialize_subjects(subjects: QuerySet[Subject] | list[Subject]) -> list[ApiSubject]:
    return [serialize_subject(subject) for subject in subjects]


def serialize_subject(subject: Subject) -> ApiSubject:
    return ApiSubject(id=subject.pk, name=subject.name)


def serialize_kind(kind: EventKind) -> ApiEventKind:
    return ApiEventKind(id=kind.pk, name=kind.name)


def serialize_time_slot(time_slot: TimeSlot) -> ApiTimeSlot:
    return ApiTimeSlot(
        id=time_slot.pk,
        alt_name=time_slot.alt_name,
        start_time=time_slot.start_time,
        end_time=time_slot.end_time,
        display_name=str(time_slot),
    )


def serialize_department(department: Department | None) -> ApiDepartment | None:
    if department is None:
        return None
    return ApiDepartment(
        id=department.pk,
        name=department.name,
        shortname=department.shortname,
        code=department.code,
    )


def serialize_schedule(schedule: Schedule) -> ApiScheduleMetadata:
    metadata = schedule.metadata
    template = schedule.schedule_template
    template_metadata = template.metadata if template else None
    department = template.department if template else None
    return ApiScheduleMetadata(
        id=schedule.pk,
        years=metadata.years if metadata else None,
        course=metadata.course if metadata else None,
        semester=metadata.semester if metadata else None,
        faculty=template_metadata.faculty if template_metadata else None,
        scope=template_metadata.scope if template_metadata else None,
        department=serialize_department(department),
    )
