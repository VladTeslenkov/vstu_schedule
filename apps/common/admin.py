from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.http import HttpResponseRedirect
from django.urls import path
from django.utils import timezone

from apps.common.models import (
    AbstractDay,
    AbstractEvent,
    AbstractEventChanges,
    DayDateOverride,
    Department,
    Event,
    EventCancel,
    EventKind,
    EventParticipant,
    EventPlace,
    Organization,
    Schedule,
    ScheduleMetadata,
    ScheduleTemplate,
    ScheduleTemplateMetadata,
    Subject,
    TimeSlot,
)
from apps.common.selectors import Selector
from apps.common.services.timetable.export.exporter import export_abstract_event_changes
from apps.common.services.timetable.load.event_importer_legacy import (
    EventImporterLegacy,
)
from apps.common.services.timetable.load.reference_importer import ReferenceImporter
from apps.common.services.timetable.read.filters import (
    DateFilter,
    EventFilter,
)
from apps.common.services.timetable.utilities.model_helpers import (
    create_common_abstract_days,
    create_common_time_slots,
)
from apps.common.services.timetable.utilities.validators import check_abstract_event
from apps.common.services.timetable.write.factories import (
    apply_day_date_override,
    rewrite_events,
)

# TODO: django.core.exceptions.ImproperlyConfigured: The model TokenProxy is abstract, so it cannot be registered with admin.
##from rest_framework.authtoken.admin import TokenAdmin 


class BaseAdmin(admin.ModelAdmin):
    readonly_fields = ("dateaccessed", "datemodified", "datecreated")

    def save_model(self, request, obj, form, change):
        if not obj.id:  # Если это новая запись
            obj.datecreated = timezone.now()
        obj.datemodified = timezone.now()
        obj.save()


@admin.register(Subject)
class SubjectAdmin(BaseAdmin):
    change_list_template = "../templates/timetable/admin/subjectChangeListExtend.html"
    list_display = ("name",)
    search_fields = ("name",)

    def get_urls(self):
        return [path("import_subject_reference/", self.import_subject_reference), *super().get_urls()]

    def import_subject_reference(self, request):
        if request.method == "POST" and request.FILES.get("subject_reference_file"):
            ReferenceImporter.import_subject_reference(request.FILES['subject_reference_file'].read())
            messages.success(request, "Импорт успешно произведён")

        return HttpResponseRedirect("../")


@admin.register(EventParticipant)
class EventParticipantAdmin(BaseAdmin):
    change_list_template = "../templates/timetable/admin/eventParticipantChangeListExtend.html"
    list_display = ("name", "role")
    search_fields = ("name", "role")
    list_filter = ("role",)

    def get_urls(self):
        return [path("import_teacher_reference/", self.import_teacher_reference),
                path("import_student_reference/", self.import_student_reference),
                *super().get_urls()]

    def import_teacher_reference(self, request):
        if request.method == "POST" and request.FILES.get("teacher_reference_file"):
            ReferenceImporter.import_teacher_reference(request.FILES['teacher_reference_file'].read())
            messages.success(request, "Импорт успешно произведён")

        return HttpResponseRedirect("../")

    def import_student_reference(self, request):
        if request.method == "POST" and request.FILES.get("student_reference_file"):
            ReferenceImporter.import_student_reference(request.FILES['student_reference_file'].read())
            messages.success(request, "Импорт успешно произведён")

        return HttpResponseRedirect("../")


@admin.register(EventPlace)
class EventPlaceAdmin(BaseAdmin):
    change_list_template = "../templates/timetable/admin/eventPlaceChangeListExtend.html"
    list_display = ("building", "room")
    search_fields = ("building", "room")
    list_filter = ("building",)

    def get_urls(self):
        return [path("import_place_reference/", self.import_place_reference), 
                *super().get_urls()]

    def import_place_reference(self, request):
        if request.method == "POST" and request.FILES.get("place_reference_file"):
            ReferenceImporter.import_place_reference(request.FILES['place_reference_file'].read())
            messages.success(request, "Импорт успешно произведён")

        return HttpResponseRedirect("../")


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

    @admin.display(description=ScheduleTemplate._meta.get_field("department").verbose_name, 
                   ordering="department__name")
    def department_name(self, obj):
        return obj.department.name


@admin.register(Schedule)
class ScheduleAdmin(BaseAdmin):
    change_list_template = "../templates/timetable/admin/scheduleChangeListExtend.html"
    list_display = ("faculty", "status", "course", "semester", "years")
    search_fields = ("schedule_template__metadata__faculty", "schedule_template__metadata__scope")
    list_filter = (
        "schedule_template__metadata__scope",
        "metadata__course",
        "status",
        "schedule_template__metadata__faculty", 
        "metadata__semester", 
        "metadata__years"
    )

    actions = ["extended_delete"]

    def get_urls(self):
        return [path("import_schedule/", self.import_schedule_data),
                path("delete_archive_schedules/", self.delete_archive_schedules),
                *super().get_urls()]

    def import_schedule_data(self, request):
        if request.method == "POST" and request.FILES.get("selected_file"):
            if "common_import" in request.POST:
                ReferenceImporter.import_schedule(request.FILES['selected_file'].read(), True)
            elif "delete_import" in request.POST:
                ReferenceImporter.import_schedule(request.FILES['selected_file'].read(), False)
            messages.success(request, "Импорт успешно произведён")

        return HttpResponseRedirect("../")

    ## TODO: add confirming page
    def delete_archive_schedules(self, request):
        Schedule.objects.filter(status=Schedule.Status.ARCHIVE).delete()

        return HttpResponseRedirect("../")

    ## TODO: ...
    @admin.action(description="Удалить выбранные Расписания и их Метаданные расписания")
    def extended_delete(modeladmin, request, queryset):
        """Deletes selected Schedules and its ScheduleMetadatas
        """
        return
        ScheduleMetadata.objects.filter(pk__in=queryset.values_list("metadata__pk", flat=True)).delete()
        queryset.delete()

        messages.success(request, "Успешно удалены")

    @admin.display(description=Schedule._meta.get_field("schedule_template").verbose_name, 
                   ordering="schedule_template__metadata__faculty")
    def faculty(self, obj):
        return obj.schedule_template.metadata.faculty

    @admin.display(description=ScheduleMetadata._meta.get_field("course").verbose_name, 
                   ordering="metadata__course")
    def course(self, obj):
        return obj.metadata.course

    @admin.display(description=ScheduleMetadata._meta.get_field("semester").verbose_name, 
                   ordering="metadata__semester")
    def semester(self, obj):
        return obj.metadata.semester

    @admin.display(description=ScheduleMetadata._meta.get_field("years").verbose_name, 
                   ordering="metadata__years")
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
    search_fields = ("participants_override__name", "subject_override__name", "places_override__building", "places_override__room", "kind_override__name", "date")
    list_filter = (EventOverridenFilter, "kind_override", "is_event_canceled")

    @admin.display(description=AbstractEvent._meta.get_field("abstract_day").verbose_name, 
                   ordering="name")
    def abstract_day(self, obj):
        return obj.abstract_event.abstract_day


@admin.register(AbstractEventChanges)
class AbstractEventChangesAdmin(BaseAdmin):
    list_display = ("datemodified", "__str__", "is_exported")
    list_filter = ("is_created", "is_deleted", "is_exported")

    #TODO: rework as buttons not actions
    actions = ["delete_exported", "export_selected", "export_not_exported"]

    @admin.action(description="Удалить экспортированные")
    def delete_exported(modeladmin, request, queryset):
        """Deletes already exported AbstractEventChanges
        """
        AbstractEventChanges.objects.filter(is_exported=True).delete()

        messages.success(request, "Успешно удалены")

    @admin.action(description="Экспортировать выбранное")
    def export_selected(modeladmin, request, queryset):
        """Export XLS form given AbstractEventChanges
        """
        response = export_abstract_event_changes(queryset)

        messages.success(request, "Успешно экспортированы")

        return response

    @admin.action(description="Экспортировать не экспортированные")
    def export_not_exported(modeladmin, request, queryset):
        """Export XLS form all not exported AbstractEventChanges
        """

        changes = AbstractEventChanges.objects.filter(is_exported=False)

        if not changes.exists():
            messages.warning(request, "Нечего экспортировать: все изменения экспортированы")

            return

        response = export_abstract_event_changes(changes)

        messages.success(request, "Успешно экспортированы")

        return response

    def changelist_view(self, request, extra_context = None):
        """Allows user to interact with specified actions without selecting models
        """

        if "action" in request.POST and request.POST["action"] in ["export_not_exported", "delete_exported"]:
            post = request.POST.copy()

            # makes request never empty
            post.update({ admin.helpers.ACTION_CHECKBOX_NAME : "0" })

            request._set_post(post) # TODO: это не очень хорошо

        return super(AbstractEventChangesAdmin, self).changelist_view(request, extra_context)


@admin.register(AbstractEvent)
class AbstractEventAdmin(BaseAdmin):
    change_list_template = "../templates/timetable/admin/abstractEventChangeListExtend.html"
    list_display = ("datemodified", "subject", "abstract_day", "time_slot")
    search_fields = ("participants__name", "subject__name", "places__building", "places__room", "kind__name")
    list_filter = ("kind__name",)

    actions = ["delete_events", "fill", "check_fields"]

    def get_urls(self):
        return [path("import_data/", self.import_event_data), *super().get_urls()]

    def import_event_data(self, request):
        if request.method == "POST" and request.FILES.get("selected_file"):
            ## TODO: when working with big files should use chunks() instead
            EventImporterLegacy.import_event_data(request.FILES['selected_file'].read())
            messages.success(request, f"Успешно произведён импорт из файла: \"{request.FILES['selected_file']}\"")

        return HttpResponseRedirect("../")

    @admin.action(description="Удалить связанные события")
    def delete_events(modeladmin, request, queryset):
        """Deletes all Events related with given AbstractEvents
        """

        Event.objects.filter(abstract_event__in=queryset).delete()
        messages.success(request, "Связанные события успешно удалены")

    @admin.action(description="Заполнить семестр")
    def fill(modeladmin, request, queryset):
        """Fills semester with Events from given AbstractEvents
        """

        if rewrite_events(queryset):
            messages.success(request, "Успешно заполнено")
        else:
            messages.error(request, "Произошла ошибка")

    @admin.action(description="Проверить на накладки в расписании")
    def check_fields(modeladmin, request, queryset):
        """Checks for double usage selected AbstractEvents field values
        """

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
    change_list_template = "../templates/timetable/admin/abstractDayChangeListExtend.html"
    list_display = ("name", "day_number")
    search_fields = ("name", "day_number")

    def get_urls(self):
        return [path("create_abstract_days/", self.create_abstract_days), *super().get_urls()]

    def create_abstract_days(self, request):
        if create_common_abstract_days():
            messages.success(request, "Стандарные абстрактные дни успешно созданы")

        return HttpResponseRedirect("../")


@admin.register(Department)
class DepartmentAdmin(BaseAdmin):
    class HasParentDepartmentFilter(admin.SimpleListFilter):
        title = "Имеет родительское подразделение"
        parameter_name = "has_parent_department"
        HAS_VALUES = ["Да", "Да"]
        HAS_NOT_VALUES = ["Нет", "Нет"]

        def lookups(self, request, model_admin):
            return (self.HAS_VALUES, self.HAS_NOT_VALUES)

        def queryset(self, request, queryset):
            if self.value() in self.HAS_VALUES:
                return queryset.filter(parent_department__isnull=False)
            elif self.value() in self.HAS_NOT_VALUES:
                return queryset.filter(parent_department__isnull=True)

            return queryset

    change_list_template = "../templates/timetable/admin/departmentChangeListExtend.html"
    list_display = ("name", "shortname", "organization_name")
    search_fields = ("name", "shortname", "organization__name")
    list_filter = (HasParentDepartmentFilter, "organization__name")

    def get_urls(self):
        return [path("import_faculty_reference/", self.import_faculty_reference),
                path("import_department_reference/", self.import_department_reference),
                *super().get_urls()]

    def import_faculty_reference(self, request):
        if request.method == "POST" and request.FILES.get("faculty_reference_file"):
            ReferenceImporter.import_faculty_reference(request.FILES['faculty_reference_file'].read())
            messages.success(request, "Импорт успешно произведён")

        return HttpResponseRedirect("../")

    def import_department_reference(self, request):
        if request.method == "POST" and request.FILES.get("department_reference_file"):
            ReferenceImporter.import_department_reference(request.FILES['department_reference_file'].read())
            messages.success(request, "Импорт успешно произведён")

        return HttpResponseRedirect("../")

    @admin.display(description=Department._meta.get_field("organization").verbose_name, 
                   ordering="organization__name")
    def organization_name(self, obj):
        return obj.organization.name


@admin.register(Organization)
class OrganizationAdmin(BaseAdmin):
    change_list_template = "../templates/timetable/admin/organizationChangeListExtend.html"
    list_display = ("name",)
    search_fields = ("name",)
    list_filter = ("name",)

    def get_urls(self):
        return [path("create_organization/", self.create_organization), *super().get_urls()]

    def create_organization(self, request):
        try:
            Organization.objects.get(name="ВолгГТУ")
        except Organization.DoesNotExist:
            Organization.objects.create(name="ВолгГТУ")
            messages.success(request, "Учреждение (ВолгГТУ) успешно создано")

        return HttpResponseRedirect("../")


@admin.register(TimeSlot)
class TimeSlotAdmin(BaseAdmin):
    change_list_template = "../templates/timetable/admin/timeSlotChangeListExtend.html"
    list_display = ("alt_name", "start_time", "end_time")
    search_fields = ("alt_name", "start_time", "end_time")
    list_filter = ("alt_name",)

    def get_urls(self):
        return [path("create_time_slots/", self.create_time_slots), *super().get_urls()]

    def create_time_slots(self, request):
        if create_common_time_slots():
            messages.success(request, "Стандарные учебные часы успешно созданы")

        return HttpResponseRedirect("../")


@admin.register(DayDateOverride)
class DayDateOverrideAdmin(BaseAdmin):
    list_display = ("day_source", "day_destination")
    search_fields = ("day_source", "day_destination")

    actions = ["override"]

    @admin.action(description="Применить переносы")
    def override(modeladmin, request, queryset):
        """Applies selected DayDateOverrides
        """
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
