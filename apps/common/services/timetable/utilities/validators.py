from django.utils.html import format_html
from django.utils.safestring import SafeText

from apps.common.models import AbstractEvent


def check_abstract_event(abstract_event : AbstractEvent) -> tuple[bool, SafeText]:
    """Check given AbstractEvent for models double usage

    Returns:
        a tuple of state of double usage and message for user notification. 
        If no model duplicating found then message will be empty
    """

    HEADER_MESSAGE_TEMPLATE = 'В запланированном событии <a href="{}">{}</a><br><br>'
    
    funcs_to_run = [
        check_for_participants_duplicate, 
        check_for_places_duplicate
    ]
    message = format_html(HEADER_MESSAGE_TEMPLATE, abstract_event.get_absolute_url(), str(abstract_event))
    is_anything_found = False

    for f in funcs_to_run:
        is_double_usage_found, m = f(abstract_event)
        
        if is_double_usage_found:
            is_anything_found = True

            message += m
            message += format_html("<br>")
    message = format_html(message[:-4])

    return is_anything_found, message

def check_for_participants_duplicate(abstract_event : AbstractEvent) -> tuple[bool, SafeText|None]:
        """Checks for EventPartcipant double usage

        Returns:
            a tuple of state of double usage and message for user notification. 
            If EventParticipants not duplicating then message will be empty
        """

        PARTICIPANTS_BASE_MESSAGE = 'ПРЕПОДАВАТЕЛИ одновременно участвуют в других запланированных событиях:<br>'
        PARTICIPANT_MESSAGE_TEMPLATE = '<a href="{}">{}</a>, '
        DUPLICATE_MESSAGE_TEMPLATE = '<a href="{}">{}</a> / {}<br>'

        other_aes = AbstractEvent.objects.filter(participants__in=abstract_event.participants.all(), 
                                                 abstract_day=abstract_event.abstract_day,
                                                 time_slot=abstract_event.time_slot).exclude(pk=abstract_event.pk).distinct()

        if not other_aes.exists():
            return False, None
        
        return_message = format_html(PARTICIPANTS_BASE_MESSAGE)
        
        for ae in other_aes:
            p_urls = format_html("")
            
            for p in abstract_event.participants.filter(pk__in=ae.participants.values_list("pk", flat=True)):
                p_urls += format_html(PARTICIPANT_MESSAGE_TEMPLATE, p.get_absolute_url(), str(p.name))
            p_urls = format_html(p_urls[:-2])
            
            return_message += format_html(DUPLICATE_MESSAGE_TEMPLATE, ae.get_absolute_url(), str(ae), p_urls)

        return True, return_message

def check_for_places_duplicate(abstract_event : AbstractEvent) -> tuple[bool, SafeText|None]:
        """Checks for EventPlace double usage

        Returns:
            a tuple of state of double usage and message for user notification. 
            If EventPlace not duplicating then message will be empty
        """

        PLACES_BASE_MESSAGE = 'АУДИТОРИИ одновременно задействованы в других запланированных событиях:<br>'
        PLACE_MESSAGE_TEMPLATE = '<a href="{}">{}</a>, '
        DUPLICATE_MESSAGE_TEMPLATE = '<a href="{}">{}</a> / {}<br>'
        
        other_aes = AbstractEvent.objects.filter(places__in=abstract_event.places.all(), 
                                                 abstract_day=abstract_event.abstract_day,
                                                 time_slot=abstract_event.time_slot).exclude(pk=abstract_event.pk).distinct()

        if not other_aes.exists():
            return False, None
        
        return_message = format_html(PLACES_BASE_MESSAGE)
        
        for ae in other_aes:
            p_urls = format_html("")
            
            for p in abstract_event.places.filter(pk__in=ae.places.values_list("pk", flat=True)):
                p_urls += format_html(PLACE_MESSAGE_TEMPLATE, p.get_absolute_url(), str(p))
            p_urls = format_html(p_urls[:-2])
            
            return_message += format_html(DUPLICATE_MESSAGE_TEMPLATE, ae.get_absolute_url(), str(ae), p_urls)

        return True, return_message
