from django.db.models.signals import m2m_changed, pre_delete, pre_init, pre_save
from django.dispatch import receiver
from django.utils import timezone

from apps.common.models import (
    AbstractEvent,
    AbstractEventChanges,
    CommonModel,
    DayDateOverride,
    Event,
    EventCancel,
)
from apps.common.services.timetable.write.factories import (
    apply_day_date_override,
    apply_event_cancel,
    refresh_related_events,
    rewrite_events,
)


@receiver(pre_save, sender=CommonModel)
def update_datemodified(sender, instance, **kwargs):
    if instance.pk:
        original = sender.objects.get(pk=instance.pk)
        has_changes = any(
            getattr(original, field) != getattr(instance, field)
            for field in instance._meta.get_fields()
            if field.name != 'datemodified'
        )
        if has_changes:
            instance.datemodified = timezone.now()
    else:
        instance.datemodified = timezone.now()


@receiver(pre_init, sender=CommonModel)
def update_dateaccessed(sender, *args, **kwargs):
    instance = kwargs.get('instance')
    if instance and instance.pk:
        instance.dateaccessed = timezone.now()
        instance.save(update_fields=['dateaccessed'])


@receiver(m2m_changed, sender=AbstractEvent.participants.through)
def participants_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
    """Writes AbstractEvent participants changes and update related Events
    """

    if action == "pre_add" or action == "pre_remove":
        if not instance.changes:
            changes = AbstractEventChanges()
            changes.initialize(instance)
            changes.save()
            instance.changes = changes
            instance.save()
    elif action == "post_add" or action == "post_remove":
        refresh_related_events(instance, update_non_m2m=False)

        instance.changes.group = AbstractEventChanges.str_from_participants(instance.get_groups())
        instance.changes.final_teachers = AbstractEventChanges.str_from_participants(instance.get_teachers())

        instance.changes.save()


@receiver(m2m_changed, sender=AbstractEvent.places.through)
def places_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
    """Writes AbstractEvent places changes and update related Events
    """

    if action == "pre_add" or action == "pre_remove":
        if not instance.changes:
            changes = AbstractEventChanges()
            changes.initialize(instance)
            changes.save()
            instance.changes = changes
            instance.save()
    elif action == "post_add" or action == "post_remove":
        refresh_related_events(instance, update_non_m2m=False)
        instance.changes.final_places = AbstractEventChanges.str_from_places(instance.places.all())
        instance.changes.save()


@receiver(pre_save, sender=AbstractEvent)
def on_abstract_event_pre_save(sender, instance, **kwargs):
    # AbsEvent created
    if instance.pk is None:
        instance.generate_changes_on_creating()
        return

    instance.update_change_model()

    if AbstractEvent.objects.get(pk=instance.pk).abstract_day != instance.abstract_day:
        rewrite_events(instance)


@receiver(pre_delete, sender=AbstractEvent)
def on_abstract_event_delete(sender, instance, **kwargs): 
    if instance.changes and instance.changes.is_created and not instance.changes.is_exported:
        instance.changes.delete()

        return

    changes = AbstractEventChanges()
    changes.initialize(instance)
    changes.is_deleted = True
    changes.save()


@receiver(pre_save, sender=EventCancel)
def on_event_cancel_date_override(sender, instance, **kwargs):
    created = instance.pk is None

    if created:
        return

    previous_cancel = EventCancel.objects.get(pk=instance.pk)

    # if EventCancel moved to other date
    # need to undo Events canceling
    if previous_cancel.date != instance.date:
        from apps.common.selectors import Selector

        reader = Selector({"event_cancel" : previous_cancel})
        reader.find_models(Event)

        for e in reader.get_found_models():
            apply_event_cancel(None, e)


@receiver(pre_delete, sender=EventCancel)
def on_event_cancel_delete(sender, instance, **kwargs):
    from apps.common.selectors import Selector

    reader = Selector({"event_cancel" : instance})
    reader.find_models(Event)
    for e in reader.get_found_models():
        apply_event_cancel(None, e)


@receiver(pre_save, sender=DayDateOverride)
def on_date_override_source_override(sender, instance, **kwargs):
    created = instance.pk is None

    if created:
        return

    previous_override = DayDateOverride.objects.get(pk=instance.pk)

    # if DayDateOverride moved to other date
    # need to detach it from Events
    if previous_override.day_source != instance.day_source:
        from apps.common.selectors import Selector

        reader = Selector({"date_override" : previous_override})
        reader.find_models(Event)
        for e in reader.get_found_models():
            apply_day_date_override(None, e)


@receiver(pre_delete, sender=DayDateOverride)
def on_day_date_override_delete(sender, instance, **kwargs):
    from apps.common.selectors import Selector

    reader = Selector({"date_override" : instance})

    reader.find_models(Event)

    for e in reader.get_found_models():
            apply_day_date_override(None, e)


@receiver(m2m_changed, sender=Event.participants_override.through)
def participants_override_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
    if (action == "post_add" or action == "post_remove") \
        and not instance.is_event_overriden and \
            list(instance.participants_override.all()) != list(instance.abstract_event.participants.all()):
            instance.is_event_overriden = True
            instance.save()


@receiver(m2m_changed, sender=Event.places_override.through)
def places_override_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
    if (action == "post_add" or action == "post_remove") and \
        not instance.is_event_overriden and \
            list(instance.places_override.all()) != list(instance.abstract_event.places.all()):
            instance.is_event_overriden = True
            instance.save()


@receiver(pre_save, sender=Event)
def on_event_save(sender, instance, **kwargs):
    created = instance.pk is None
    previous_event = None

    if not created:
        previous_event = Event.objects.get(pk=instance.pk)

        # check for override by non m2m fields
        if not instance.is_event_overriden and (instance.kind_override != instance.abstract_event.kind or \
                instance.subject_override != instance.abstract_event.subject or \
                instance.time_slot_override != instance.abstract_event.time_slot or \
                (instance.is_event_canceled and not instance.event_cancel)):
                instance.is_event_overriden = True

    instance.check_date_interactions()

    # if Event was created or date changed
    # need to check for event canceling
    if created or previous_event.date != instance.date:
        instance.check_canceling()

    # if EventCancel was manualy setted in Event
    # but is_event_canceled not checked
    # make Event canceled
    if not created and not instance.is_event_canceled and not previous_event.event_cancel and instance.event_cancel:
        instance.is_event_canceled = True
