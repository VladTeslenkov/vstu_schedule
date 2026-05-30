# API Compatibility

`apps/api/schemas.py` and `apps/api/services/serialization.py` are the public
timetable API contract.

When changing timetable ORM models, relations, status/choice values, or helper
methods used by API serialization, check and update API DTOs, serializers, and
contract tests.

Public DTO fields must not be removed or renamed incompatibly without explicit
API versioning or an agreed migration plan. Internal Django model fields should
not leak into the public API automatically.
