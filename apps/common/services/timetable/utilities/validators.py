from collections.abc import Callable
from typing import Any, cast

from django.utils.html import format_html
from django.utils.safestring import SafeText, mark_safe

from apps.common.models import AbstractEvent


def check_abstract_event(abstract_event: AbstractEvent) -> tuple[bool, SafeText]:
    """Check given AbstractEvent for models double usage

    Returns:
        a tuple of state of double usage and message for user notification.
        If no model duplicating found then message will be empty
    """

    HEADER_MESSAGE_TEMPLATE = 'В запланированном событии <a href="{}">{}</a><br><br>'

    funcs_to_run: list[Callable[[AbstractEvent], tuple[bool, SafeText]]] = [
        check_for_participants_duplicate,
        check_for_places_duplicate,
    ]
    message_parts = [
        str(
            format_html(
                HEADER_MESSAGE_TEMPLATE, abstract_event.get_absolute_url(), str(abstract_event)
            )
        ),
    ]
    is_anything_found = False

    for f in funcs_to_run:
        is_double_usage_found, m = f(abstract_event)

        if is_double_usage_found:
            is_anything_found = True

            message_parts.append(str(m))
            message_parts.append("<br>")

    message = "".join(message_parts).removesuffix("<br>")

    return is_anything_found, cast(SafeText, mark_safe(message))


def check_for_participants_duplicate(abstract_event: AbstractEvent) -> tuple[bool, SafeText]:
    """Checks for EventPartcipant double usage

    Returns:
        a tuple of state of double usage and message for user notification.
        If EventParticipants not duplicating then message will be empty
    """

    PARTICIPANTS_BASE_MESSAGE = (
        "ПРЕПОДАВАТЕЛИ одновременно участвуют в других запланированных событиях:<br>"
    )
    PARTICIPANT_MESSAGE_TEMPLATE = '<a href="{}">{}</a>, '
    DUPLICATE_MESSAGE_TEMPLATE = '<a href="{}">{}</a> / {}<br>'

    participants = cast(Any, abstract_event.participants)
    other_aes = (
        cast(Any, AbstractEvent)
        .objects.filter(
            participants__in=participants.all(),
            abstract_day=abstract_event.abstract_day,
            time_slot=abstract_event.time_slot,
        )
        .exclude(pk=abstract_event.pk)
        .distinct()
    )

    if not other_aes.exists():
        return False, cast(SafeText, mark_safe(""))

    message_parts = [PARTICIPANTS_BASE_MESSAGE]

    for ae in other_aes:
        participant_links = [
            str(format_html(PARTICIPANT_MESSAGE_TEMPLATE, p.get_absolute_url(), str(p.name)))
            for p in participants.filter(
                pk__in=cast(Any, ae.participants).values_list("pk", flat=True)
            )
        ]
        p_urls = cast(SafeText, mark_safe("".join(participant_links).removesuffix(", ")))

        message_parts.append(
            str(format_html(DUPLICATE_MESSAGE_TEMPLATE, ae.get_absolute_url(), str(ae), p_urls))
        )

    return True, cast(SafeText, mark_safe("".join(message_parts)))


def check_for_places_duplicate(abstract_event: AbstractEvent) -> tuple[bool, SafeText]:
    """Checks for EventPlace double usage

    Returns:
        a tuple of state of double usage and message for user notification.
        If EventPlace not duplicating then message will be empty
    """

    PLACES_BASE_MESSAGE = (
        "АУДИТОРИИ одновременно задействованы в других запланированных событиях:<br>"
    )
    PLACE_MESSAGE_TEMPLATE = '<a href="{}">{}</a>, '
    DUPLICATE_MESSAGE_TEMPLATE = '<a href="{}">{}</a> / {}<br>'

    places = cast(Any, abstract_event.places)
    other_aes = (
        cast(Any, AbstractEvent)
        .objects.filter(
            places__in=places.all(),
            abstract_day=abstract_event.abstract_day,
            time_slot=abstract_event.time_slot,
        )
        .exclude(pk=abstract_event.pk)
        .distinct()
    )

    if not other_aes.exists():
        return False, cast(SafeText, mark_safe(""))

    message_parts = [PLACES_BASE_MESSAGE]

    for ae in other_aes:
        place_links = [
            str(format_html(PLACE_MESSAGE_TEMPLATE, p.get_absolute_url(), str(p)))
            for p in places.filter(pk__in=cast(Any, ae.places).values_list("pk", flat=True))
        ]
        p_urls = cast(SafeText, mark_safe("".join(place_links).removesuffix(", ")))

        message_parts.append(
            str(format_html(DUPLICATE_MESSAGE_TEMPLATE, ae.get_absolute_url(), str(ae), p_urls))
        )

    return True, cast(SafeText, mark_safe("".join(message_parts)))
