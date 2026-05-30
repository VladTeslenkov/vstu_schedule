from collections.abc import Iterable
from typing import Any, ClassVar

from django.conf import settings
from django.db.models import Model, Q, QuerySet

from apps.api.schemas import ApiModelRecord
from apps.common.models import (
    AbstractDay,
    AbstractEvent,
    AbstractEventChanges,
    DayDateOverride,
    Department,
    Event,
    EventCancel,
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


class ModelEndpointSpec:
    model: type[Model]
    fields: ClassVar[tuple[str, ...]]
    search_fields: ClassVar[tuple[str, ...]]
    select_related: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def get_queryset(cls, params) -> QuerySet:
        queryset = cls.model.objects.all()
        if cls.select_related:
            queryset = queryset.select_related(*cls.select_related)

        record_id = params.get("id")
        if record_id:
            queryset = queryset.filter(pk=record_id)

        query = params.get("q", "").strip()
        if query:
            q_filter = Q()
            for field in cls.search_fields:
                q_filter |= Q(**{f"{field}__icontains": query})
            queryset = queryset.filter(q_filter)

        for field in cls.fields:
            value = params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})

        limit = _parse_limit(params.get("limit"))
        return queryset.order_by("pk")[:limit]


def serialize_model_records(
    records: Iterable[Model], fields: Iterable[str]
) -> list[ApiModelRecord]:
    return [
        ApiModelRecord(
            id=record.pk,
            display_name=str(record),
            fields={field: _field_value(record, field) for field in fields},
        )
        for record in records
    ]


def _field_value(record: Model, field: str) -> Any:
    value = getattr(record, field)
    if isinstance(value, Model):
        return value.pk
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _parse_limit(value: str | None) -> int:
    if not value:
        return settings.API_MODEL_LIST_LIMIT
    try:
        limit = int(value)
    except ValueError:
        return settings.API_MODEL_LIST_LIMIT
    return max(1, min(limit, settings.API_MODEL_LIST_LIMIT))


class OrganizationSpec(ModelEndpointSpec):
    model = Organization
    fields = ("name",)
    search_fields = ("name",)


class DepartmentSpec(ModelEndpointSpec):
    model = Department
    fields = ("name", "shortname", "code", "organization_id", "parent_department_id")
    search_fields = ("name", "shortname", "code")
    select_related = ("organization", "parent_department")


class SubjectSpec(ModelEndpointSpec):
    model = Subject
    fields = ("name",)
    search_fields = ("name",)


class TimeSlotSpec(ModelEndpointSpec):
    model = TimeSlot
    fields = ("alt_name", "start_time", "end_time")
    search_fields = ("alt_name",)


class EventPlaceSpec(ModelEndpointSpec):
    model = EventPlace
    fields = ("building", "room")
    search_fields = ("building", "room")


class EventKindSpec(ModelEndpointSpec):
    model = EventKind
    fields = ("name",)
    search_fields = ("name",)


class AbstractDaySpec(ModelEndpointSpec):
    model = AbstractDay
    fields = ("day_number", "name")
    search_fields = ("name",)


class ScheduleTemplateMetadataSpec(ModelEndpointSpec):
    model = ScheduleTemplateMetadata
    fields = ("faculty", "scope")
    search_fields = ("faculty", "scope")


class ScheduleMetadataSpec(ModelEndpointSpec):
    model = ScheduleMetadata
    fields = ("years", "course", "semester")
    search_fields = ("years",)


class ScheduleTemplateSpec(ModelEndpointSpec):
    model = ScheduleTemplate
    fields = (
        "metadata_id",
        "repetition_period",
        "repeatable",
        "aligned_by_week_day",
        "department_id",
    )
    search_fields = ("department__name", "department__shortname", "metadata__faculty")
    select_related = ("metadata", "department")


class ScheduleSpec(ModelEndpointSpec):
    model = Schedule
    fields = (
        "metadata_id",
        "status",
        "start_date",
        "end_date",
        "starting_day_number_id",
        "schedule_template_id",
    )
    search_fields = ("metadata__years", "schedule_template__metadata__faculty")
    select_related = ("metadata", "starting_day_number", "schedule_template")


class EventParticipantSpec(ModelEndpointSpec):
    model = EventParticipant
    fields = ("name", "role", "is_group", "department_id")
    search_fields = ("name", "role", "department__name", "department__shortname")
    select_related = ("department",)


class AbstractEventChangesSpec(ModelEndpointSpec):
    model = AbstractEventChanges
    fields = ("group", "date_time", "subject", "is_created", "is_deleted", "is_exported")
    search_fields = ("group", "date_time", "subject")


class AbstractEventSpec(ModelEndpointSpec):
    model = AbstractEvent
    fields = (
        "kind_id",
        "subject_id",
        "abstract_day_id",
        "time_slot_id",
        "holds_on_date",
        "schedule_id",
        "changes_id",
    )
    search_fields = ("subject__name",)
    select_related = ("kind", "subject", "abstract_day", "time_slot", "schedule", "changes")


class EventCancelSpec(ModelEndpointSpec):
    model = EventCancel
    fields = ("date", "department_id")
    search_fields = ("department__name", "department__shortname")
    select_related = ("department",)


class DayDateOverrideSpec(ModelEndpointSpec):
    model = DayDateOverride
    fields = ("day_source", "day_destination", "department_id")
    search_fields = ("department__name", "department__shortname")
    select_related = ("department",)


class EventSpec(ModelEndpointSpec):
    model = Event
    fields = (
        "date",
        "date_override_id",
        "kind_override_id",
        "subject_override_id",
        "time_slot_override_id",
        "abstract_event_id",
        "is_event_canceled",
        "event_cancel_id",
        "is_event_overriden",
    )
    search_fields = ("subject_override__name", "kind_override__name")
    select_related = (
        "date_override",
        "kind_override",
        "subject_override",
        "time_slot_override",
        "abstract_event",
        "event_cancel",
    )
