from django.contrib.admin.views.decorators import staff_member_required
from dmr.openapi import OpenAPIConfig, build_schema
from dmr.openapi.views import OpenAPIJsonView, SwaggerView
from dmr.routing import Router, path

from apps.api.controllers import (
    ExportController,
    ReferenceController,
    ReferenceDisciplinesController,
    ReferenceGroupsController,
    ReferencePlacesController,
    ReferenceTeachersController,
    TokenController,
)
from apps.api.schedule_controllers import (
    AbstractDayController,
    AbstractEventChangesController,
    AbstractEventController,
    DayDateOverrideController,
    DepartmentController,
    EventCancelController,
    EventController,
    EventKindController,
    EventParticipantController,
    EventPlaceController,
    OrganizationController,
    ScheduleController,
    ScheduleMetadataController,
    ScheduleTemplateController,
    ScheduleTemplateMetadataController,
    SubjectController,
    TimeSlotController,
)

app_name = "api"

router = Router(
    "api/",
    [
        path("token/", TokenController.as_view(), name="token"),
        path("export/", ExportController.as_view(), name="export"),
        path("reference/", ReferenceController.as_view(), name="reference"),
        path("reference/groups/", ReferenceGroupsController.as_view(), name="reference_groups"),
        path(
            "reference/teachers/",
            ReferenceTeachersController.as_view(),
            name="reference_teachers",
        ),
        path(
            "reference/disciplines/",
            ReferenceDisciplinesController.as_view(),
            name="reference_disciplines",
        ),
        path("reference/places/", ReferencePlacesController.as_view(), name="reference_places"),
        path("organization/", OrganizationController.as_view(), name="organization"),
        path("department/", DepartmentController.as_view(), name="department"),
        path("subject/", SubjectController.as_view(), name="subject"),
        path("time-slot/", TimeSlotController.as_view(), name="time_slot"),
        path("event-place/", EventPlaceController.as_view(), name="event_place"),
        path("event-kind/", EventKindController.as_view(), name="event_kind"),
        path("abstract-day/", AbstractDayController.as_view(), name="abstract_day"),
        path(
            "schedule-template-metadata/",
            ScheduleTemplateMetadataController.as_view(),
            name="schedule_template_metadata",
        ),
        path("schedule-metadata/", ScheduleMetadataController.as_view(), name="schedule_metadata"),
        path("schedule-template/", ScheduleTemplateController.as_view(), name="schedule_template"),
        path("schedule/", ScheduleController.as_view(), name="schedule"),
        path("event-participant/", EventParticipantController.as_view(), name="event_participant"),
        path(
            "abstract-event-changes/",
            AbstractEventChangesController.as_view(),
            name="abstract_event_changes",
        ),
        path("abstract-event/", AbstractEventController.as_view(), name="abstract_event"),
        path("event-cancel/", EventCancelController.as_view(), name="event_cancel"),
        path("day-date-override/", DayDateOverrideController.as_view(), name="day_date_override"),
        path("event/", EventController.as_view(), name="event"),
    ],
)

schema = build_schema(
    router,
    config=OpenAPIConfig(
        title="VSTU Schedule API",
        version="1.0.0",
        description="Public export/reference API and authenticated timetable model read API.",
    ),
)

urlpatterns = [
    *router.urls,
    path(
        "schema/",
        staff_member_required(OpenAPIJsonView.as_view(schema=schema)),
        name="schema",
    ),
    path(
        "docs/",
        staff_member_required(SwaggerView.as_view(schema=schema)),
        name="docs",
    ),
]
