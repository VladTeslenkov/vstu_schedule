from django import template
from django.utils.safestring import SafeString, mark_safe

from apps.common.services.alerts import render_alert_body

register = template.Library()


@register.filter(name="alert_body_markdown")
def alert_body_markdown(value: object) -> SafeString:
    """Render an alert body after markdown-it has escaped unsafe input."""
    return mark_safe(render_alert_body(str(value)))
