from typing import Any, ClassVar, cast

from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from apps.common.models import (
    AbstractDay,
    AbstractEvent,
    AbstractEventChanges,
    Alert,
    DayDateOverride,
    Department,
    Event,
    EventCancel,
    EventKind,
    EventParticipant,
    EventPlace,
    FileVersion,
    Organization,
    Schedule,
    ScheduleMetadata,
    ScheduleTemplate,
    ScheduleTemplateMetadata,
    Setting,
    Subject,
    Tag,
    TimeSlot,
    TimetableFileImport,
)
from apps.common.selectors import Selector
from apps.common.services.timetable.export.exporter import export_abstract_event_changes
from apps.common.services.timetable.read.filters import (
    DateFilter,
    EventFilter,
)
from apps.common.services.timetable.utilities.validators import check_abstract_event
from apps.common.services.timetable.write.factories import (
    apply_day_date_override,
    rewrite_events,
)

# TODO: django.core.exceptions.ImproperlyConfigured: The model TokenProxy is abstract, so it cannot be registered with admin.
##from rest_framework.authtoken.admin import TokenAdmin


def get_model_field_verbose_name(model: type[Any], field_name: str) -> str:
    return str(cast(Any, model._meta.get_field(field_name)).verbose_name)


class BaseAdmin(admin.ModelAdmin):
    readonly_fields = ("dateaccessed", "datemodified", "datecreated")

    def save_model(self, request, obj, form, change):
        if not obj.id:  # Если это новая запись
            obj.datecreated = timezone.now()
        obj.datemodified = timezone.now()
        obj.save()


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "is_enabled",
        "is_admin",
        "is_dismissible",
        "starts_at",
        "expires_at",
        "created_at",
    )
    list_filter = (
        "category",
        "is_enabled",
        "is_admin",
        "is_dismissible",
        "starts_at",
        "expires_at",
    )
    search_fields = ("title", "body", "title_en", "body_en")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("title", "body", "title_en", "body_en")}),
        ("Display", {"fields": ("category", "is_enabled", "is_admin", "is_dismissible")}),
        ("Schedule", {"fields": ("starts_at", "expires_at")}),
        ("System", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    search_fields = ("name", "category")
    list_filter = ("category",)


@admin.register(FileVersion)
class FileVersionAdmin(admin.ModelAdmin):
    list_display = ("resource", "mimetype", "timestamp", "last_changed", "hashsum")
    search_fields = ("resource__name", "resource__path", "url", "hashsum")
    list_filter = ("mimetype", "timestamp", "last_changed")
    readonly_fields = ("timestamp",)


@admin.register(TimetableFileImport)
class TimetableFileImportAdmin(admin.ModelAdmin):
    list_display = ("file_version", "status", "started_at", "finished_at")
    search_fields = (
        "file_version__resource__name",
        "file_version__resource__path",
        "error",
    )
    list_filter = ("status", "started_at", "finished_at")
    readonly_fields = ("started_at",)


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "description")
    search_fields = ("key", "value", "description")


@admin.register(Subject)
class SubjectAdmin(BaseAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(EventParticipant)
class EventParticipantAdmin(BaseAdmin):
    list_display = ("name", "role")
    search_fields = ("name", "role")
    list_filter = ("role",)


@admin.register(EventPlace)
class EventPlaceAdmin(BaseAdmin):
    list_display = ("building", "room")
    search_fields = ("building", "room")
    list_filter = ("building",)


@admin.register(EventKind)
class EventKindAdmin(BaseAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(ScheduleTemplateMetadata)
class ScheduleTemplateMetadataAdmin(BaseAdmin):
    list_display = ("faculty", "scope")
    search_fields = ("faculty", "scope")
    list_filter = ("faculty", "scope")


@admin.register(ScheduleMetadata)
class ScheduleMetadataAdmin(BaseAdmin):
    list_display = ("years", "course", "semester")
    search_fields = ("years", "course", "semester")
    list_filter = ("years", "course", "semester")


@admin.register(ScheduleTemplate)
class ScheduleTemplateAdmin(BaseAdmin):
    list_display = ("repetition_period", "department_name", "aligned_by_week_day")
    search_fields = ("repetition_period", "department__name", "aligned_by_week_day")
    list_filter = ("metadata__faculty", "metadata__scope")

    @admin.display(
        description=get_model_field_verbose_name(ScheduleTemplate, "department"),
        ordering="department__name",
    )
    def department_name(self, obj):
        return obj.department.name


@admin.register(Schedule)
class ScheduleAdmin(BaseAdmin):
    list_display = ("faculty", "status", "course", "semester", "years")
    search_fields = ("schedule_template__metadata__faculty", "schedule_template__metadata__scope")
    list_filter = (
        "schedule_template__metadata__scope",
        "metadata__course",
        "status",
        "schedule_template__metadata__faculty",
        "metadata__semester",
        "metadata__years",
    )

    actions = ("extended_delete",)

    ## TODO: ...
    @admin.action(description="Удалить выбранные Расписания и их Метаданные расписания")
    def extended_delete(modeladmin, request, queryset):
        """Deletes selected Schedules and its ScheduleMetadatas"""
        metadata_pks = list(queryset.values_list("metadata__pk", flat=True))
        queryset.delete()
        ScheduleMetadata.objects.filter(pk__in=metadata_pks).delete()

        messages.success(request, "Успешно удалены")

    @admin.display(
        description=get_model_field_verbose_name(Schedule, "schedule_template"),
        ordering="schedule_template__metadata__faculty",
    )
    def faculty(self, obj):
        return obj.schedule_template.metadata.faculty

    @admin.display(
        description=get_model_field_verbose_name(ScheduleMetadata, "course"),
        ordering="metadata__course",
    )
    def course(self, obj):
        return obj.metadata.course

    @admin.display(
        description=get_model_field_verbose_name(ScheduleMetadata, "semester"),
        ordering="metadata__semester",
    )
    def semester(self, obj):
        return obj.metadata.semester

    @admin.display(
        description=get_model_field_verbose_name(ScheduleMetadata, "years"),
        ordering="metadata__years",
    )
    def years(self, obj):
        return obj.metadata.years


@admin.register(Event)
class EventAdmin(BaseAdmin):
    class EventOverridenFilter(admin.SimpleListFilter):
        title = "Событие перезаписано"
        parameter_name = "is_overriden"
        OVERRIDEN_VALUES = ("Перезаписан", "Перезаписаны")
        NOT_OVERRIDEN_VALUES = ("Не перезаписан", "Не перезаписаны")

        def lookups(self, request, model_admin):
            return (self.OVERRIDEN_VALUES, self.NOT_OVERRIDEN_VALUES)

        def queryset(self, request, queryset):
            if self.value() in self.OVERRIDEN_VALUES:
                return queryset.filter(**EventFilter.overriden())
            elif self.value() in self.NOT_OVERRIDEN_VALUES:
                return queryset.filter(**EventFilter.not_overriden())

            return queryset

    list_display = ("subject_override", "date", "abstract_day", "time_slot_override")
    search_fields = (
        "participants_override__name",
        "subject_override__name",
        "places_override__building",
        "places_override__room",
        "kind_override__name",
        "date",
    )
    list_filter = (EventOverridenFilter, "kind_override", "is_event_canceled")

    @admin.display(
        description=get_model_field_verbose_name(AbstractEvent, "abstract_day"),
        ordering="name",
    )
    def abstract_day(self, obj):
        return obj.abstract_event.abstract_day


@admin.register(AbstractEventChanges)
class AbstractEventChangesAdmin(BaseAdmin):
    list_display = ("datemodified", "__str__", "is_exported")
    list_filter = ("is_created", "is_deleted", "is_exported")

    # TODO: rework as buttons not actions
    actions = ("delete_exported", "export_selected", "export_not_exported")
    actions_without_selection: ClassVar[frozenset[str]] = frozenset(
        {"delete_exported", "export_not_exported"}
    )

    @admin.action(description="Удалить экспортированные")
    def delete_exported(modeladmin, request, queryset):
        """Deletes already exported AbstractEventChanges"""
        AbstractEventChanges.objects.filter(is_exported=True).delete()

        messages.success(request, "Успешно удалены")

    @admin.action(description="Экспортировать выбранное")
    def export_selected(modeladmin, request, queryset):
        """Export XLS form given AbstractEventChanges"""
        response = export_abstract_event_changes(queryset)

        messages.success(request, "Успешно экспортированы")

        return response

    @admin.action(description="Экспортировать не экспортированные")
    def export_not_exported(modeladmin, request, queryset):
        """Export XLS form all not exported AbstractEventChanges"""

        changes = AbstractEventChanges.objects.filter(is_exported=False)

        if not changes.exists():
            messages.warning(request, "Нечего экспортировать: все изменения экспортированы")

            return

        response = export_abstract_event_changes(changes)

        messages.success(request, "Успешно экспортированы")

        return response

    def _get_requested_action_name(self, request: HttpRequest) -> str | None:
        try:
            action_index = int(request.POST.get("index", 0))
        except ValueError:
            action_index = 0

        try:
            return request.POST.getlist("action")[action_index]
        except IndexError:
            return None

    def changelist_view(
        self,
        request: HttpRequest,
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        action_name = self._get_requested_action_name(request)
        if (
            request.method == "POST"
            and action_name in self.actions_without_selection
            and not request.POST.getlist(ACTION_CHECKBOX_NAME)
        ):
            post = request.POST.copy()
            post.update({ACTION_CHECKBOX_NAME: "0"})
            cast(Any, request).POST = post

        return super().changelist_view(request, extra_context)


@admin.register(AbstractEvent)
class AbstractEventAdmin(BaseAdmin):
    list_display = ("datemodified", "subject", "abstract_day", "time_slot")
    search_fields = (
        "participants__name",
        "subject__name",
        "places__building",
        "places__room",
        "kind__name",
    )
    list_filter = ("kind__name",)

    actions = ("delete_events", "fill", "check_fields")

    @admin.action(description="Удалить связанные события")
    def delete_events(modeladmin, request, queryset):
        """Deletes all Events related with given AbstractEvents"""

        Event.objects.filter(abstract_event__in=queryset).delete()
        messages.success(request, "Связанные события успешно удалены")

    @admin.action(description="Заполнить семестр")
    def fill(modeladmin, request, queryset):
        """Fills semester with Events from given AbstractEvents"""

        if rewrite_events(queryset):
            messages.success(request, "Успешно заполнено")
        else:
            messages.error(request, "Произошла ошибка")

    @admin.action(description="Проверить на накладки в расписании")
    def check_fields(modeladmin, request, queryset):
        """Checks for double usage selected AbstractEvents field values"""

        is_any_warning_shown = False

        for ae in queryset:
            is_double_usage_found, message = check_abstract_event(ae)

            if is_double_usage_found:
                is_any_warning_shown = True

                messages.warning(request, message)

        if not is_any_warning_shown:
            messages.success(request, "В выбранных запланированных событиях накладки не найдены")


@admin.register(AbstractDay)
class AbstractDayAdmin(BaseAdmin):
    list_display = ("name", "day_number")
    search_fields = ("name", "day_number")


@admin.register(Department)
class DepartmentAdmin(BaseAdmin):
    class HasParentDepartmentFilter(admin.SimpleListFilter):
        title = "Имеет родительское подразделение"
        parameter_name = "has_parent_department"
        HAS_VALUES: ClassVar[tuple[str, str]] = ("Да", "Да")
        HAS_NOT_VALUES: ClassVar[tuple[str, str]] = ("Нет", "Нет")

        def lookups(self, request, model_admin):
            return (self.HAS_VALUES, self.HAS_NOT_VALUES)

        def queryset(self, request, queryset):
            if self.value() in self.HAS_VALUES:
                return queryset.filter(parent_department__isnull=False)
            elif self.value() in self.HAS_NOT_VALUES:
                return queryset.filter(parent_department__isnull=True)

            return queryset

    list_display = ("name", "shortname", "organization_name")
    search_fields = ("name", "shortname", "organization__name")
    list_filter = (HasParentDepartmentFilter, "organization__name")

    @admin.display(
        description=get_model_field_verbose_name(Department, "organization"),
        ordering="organization__name",
    )
    def organization_name(self, obj):
        return obj.organization.name


@admin.register(Organization)
class OrganizationAdmin(BaseAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    list_filter = ("name",)


@admin.register(TimeSlot)
class TimeSlotAdmin(BaseAdmin):
    list_display = ("alt_name", "start_time", "end_time")
    search_fields = ("alt_name", "start_time", "end_time")
    list_filter = ("alt_name",)


@admin.register(DayDateOverride)
class DayDateOverrideAdmin(BaseAdmin):
    list_display = ("day_source", "day_destination")
    search_fields = ("day_source", "day_destination")

    actions = ("override",)

    @admin.action(description="Применить переносы")
    def override(modeladmin, request, queryset):
        """Applies selected DayDateOverrides"""
        for ddo in queryset:
            reader = Selector(DateFilter.from_singe_date(ddo.day_source))
            reader.add_filter(EventFilter.by_department(ddo.department))

            reader.find_models(Event)

            for e in reader.get_found_models():
                apply_day_date_override(ddo, e)

        messages.success(request, "Успешно перенесены")


@admin.register(EventCancel)
class EventCancelAdmin(BaseAdmin):
    list_display = ("date", "department")
    search_fields = ("date", "department")


# TODO: django.core.exceptions.ImproperlyConfigured: The model TokenProxy is abstract, so it cannot be registered with admin.
##TokenAdmin.raw_id_fields = ["user"]
