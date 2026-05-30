from datetime import date, datetime, time
from typing import Any

import msgspec


class ApiDepartment(msgspec.Struct):
    id: int | None
    name: str | None
    shortname: str | None
    code: str | None


class ApiParticipant(msgspec.Struct):
    id: int
    name: str
    role: str
    is_group: bool
    department: ApiDepartment | None = None


class ApiPlace(msgspec.Struct):
    id: int
    building: str
    room: str
    display_name: str


class ApiSubject(msgspec.Struct):
    id: int
    name: str


class ApiEventKind(msgspec.Struct):
    id: int
    name: str


class ApiTimeSlot(msgspec.Struct):
    id: int
    alt_name: str | None
    start_time: time | None
    end_time: time | None
    display_name: str


class ApiScheduleMetadata(msgspec.Struct):
    id: int | None
    years: str | None
    course: int | None
    semester: int | None
    faculty: str | None
    scope: str | None
    department: ApiDepartment | None


class ApiEvent(msgspec.Struct):
    id: int
    date: date | None
    abstract_event_id: int | None
    subject: ApiSubject | None
    kind: ApiEventKind | None
    time_slot: ApiTimeSlot | None
    groups: list[ApiParticipant]
    teachers: list[ApiParticipant]
    places: list[ApiPlace]
    is_canceled: bool
    is_overridden: bool
    schedule: ApiScheduleMetadata | None = None


class ApiReference(msgspec.Struct):
    groups: list[ApiParticipant]
    teachers: list[ApiParticipant]
    disciplines: list[ApiSubject]
    places: list[ApiPlace]


class ApiExportResponse(msgspec.Struct):
    count: int
    filters: dict[str, Any]
    events: list[ApiEvent]


class ApiTokenRequest(msgspec.Struct):
    client_id: str
    client_secret: str


class ApiTokenResponse(msgspec.Struct):
    access_token: str
    token_type: str
    expires_in: int
    scope: str


class ApiClientSummary(msgspec.Struct):
    id: int
    name: str
    client_id: str
    is_active: bool
    created_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None


class ApiModelRecord(msgspec.Struct):
    id: int
    display_name: str
    fields: dict[str, Any]
