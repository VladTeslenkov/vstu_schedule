from dmr import Controller, modify
from dmr.plugins.msgspec import MsgspecSerializer

from apps.api.schemas import ApiModelRecord
from apps.api.services.auth import ApiClientTokenSyncAuth, StaffSessionSyncAuth
from apps.api.services.model_records import (
    AbstractDaySpec,
    AbstractEventChangesSpec,
    AbstractEventSpec,
    DayDateOverrideSpec,
    DepartmentSpec,
    EventCancelSpec,
    EventKindSpec,
    EventParticipantSpec,
    EventPlaceSpec,
    EventSpec,
    ModelEndpointSpec,
    OrganizationSpec,
    ScheduleMetadataSpec,
    ScheduleSpec,
    ScheduleTemplateMetadataSpec,
    ScheduleTemplateSpec,
    SubjectSpec,
    TimeSlotSpec,
    serialize_model_records,
)


class AuthenticatedModelController(Controller[MsgspecSerializer]):
    serializer = MsgspecSerializer
    spec: type[ModelEndpointSpec]

    @modify(auth=[ApiClientTokenSyncAuth(), StaffSessionSyncAuth()])
    def get(self) -> list[ApiModelRecord]:
        """List model records with basic id, q, limit, and field filters."""
        records = self.spec.get_queryset(self.request.GET)
        return serialize_model_records(records, self.spec.fields)


class OrganizationController(AuthenticatedModelController):
    spec = OrganizationSpec


class DepartmentController(AuthenticatedModelController):
    spec = DepartmentSpec


class SubjectController(AuthenticatedModelController):
    spec = SubjectSpec


class TimeSlotController(AuthenticatedModelController):
    spec = TimeSlotSpec


class EventPlaceController(AuthenticatedModelController):
    spec = EventPlaceSpec


class EventKindController(AuthenticatedModelController):
    spec = EventKindSpec


class AbstractDayController(AuthenticatedModelController):
    spec = AbstractDaySpec


class ScheduleTemplateMetadataController(AuthenticatedModelController):
    spec = ScheduleTemplateMetadataSpec


class ScheduleMetadataController(AuthenticatedModelController):
    spec = ScheduleMetadataSpec


class ScheduleTemplateController(AuthenticatedModelController):
    spec = ScheduleTemplateSpec


class ScheduleController(AuthenticatedModelController):
    spec = ScheduleSpec


class EventParticipantController(AuthenticatedModelController):
    spec = EventParticipantSpec


class AbstractEventChangesController(AuthenticatedModelController):
    spec = AbstractEventChangesSpec


class AbstractEventController(AuthenticatedModelController):
    spec = AbstractEventSpec


class EventCancelController(AuthenticatedModelController):
    spec = EventCancelSpec


class DayDateOverrideController(AuthenticatedModelController):
    spec = DayDateOverrideSpec


class EventController(AuthenticatedModelController):
    spec = EventSpec
