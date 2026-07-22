from datetime import timedelta

from django.utils import timezone
from markdown_it import MarkdownIt

from apps.common.models import Alert

_ALERT_MARKDOWN = MarkdownIt(
    "commonmark",
    {
        "breaks": True,
        "html": False,
    },
).disable("image")


def render_alert_body(body: str) -> str:
    """Render the supported safe inline Markdown subset for an alert body."""
    return _ALERT_MARKDOWN.renderInline(body)


def create_alert(
    *,
    title: str,
    body: str,
    category: Alert.Category = Alert.Category.NOTICE,
    is_admin: bool = False,
    is_dismissible: bool = True,
    title_en: str = "",
    body_en: str = "",
    ttl: timedelta | None = None,
) -> Alert:
    expires_at = timezone.now() + ttl if ttl is not None else None
    return Alert.objects.create(
        title=title,
        body=body,
        title_en=title_en,
        body_en=body_en,
        category=category,
        is_admin=is_admin,
        is_dismissible=is_dismissible,
        expires_at=expires_at,
    )
