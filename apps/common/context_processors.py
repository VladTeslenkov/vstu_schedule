from django.db import DatabaseError
from django.http import HttpRequest

from apps.common.selectors import admin_alerts as get_admin_alerts


def admin_alerts(request: HttpRequest) -> dict[str, object]:
    if not request.path.startswith("/panel/") or not getattr(request.user, "is_staff", False):
        return {}

    try:
        return {"admin_alerts": get_admin_alerts()}
    except DatabaseError:
        return {"admin_alerts": []}
