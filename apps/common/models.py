from typing import Optional, Self

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse


class CommonModel(models.Model):
    idnumber = models.CharField(
        unique=True,
        blank=True,
        null=True,
        max_length=260,
        verbose_name="Уникальный строковый идентификатор",
    )
    datecreated = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания записи")
    datemodified = models.DateTimeField(auto_now_add=True, verbose_name="Дата изменения записи")
    dateaccessed = models.DateTimeField(
        null=True, blank=True, verbose_name="Дата доступа к записи"
    )
    author = models.ForeignKey(
        User, blank=True, null=True, on_delete=models.SET_NULL, verbose_name="Автор записи"
    )
    note = models.TextField(
        null=True, blank=True, verbose_name="Комментарий для этой записи", max_length=1024
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.__repr__()

    @classmethod
    def last_modified_record(cls) -> Optional[Self]:
        return cls.objects.order_by("-datemodified").first()



class Subject(CommonModel):
    name = models.CharField(max_length=256, verbose_name="Название")

    class Meta: # type: ignore
        verbose_name = "Предмет"
        verbose_name_plural = "Предметы"


    def __repr__(self):
        return str(self.name)


class TimeSlot(CommonModel):
    alt_name = models.TextField(blank=True, null=True, verbose_name="Академ. часы пары")
    start_time = models.TimeField(verbose_name="Время начала")
    end_time = models.TimeField(blank=True, null=True, verbose_name="Время окончания")

    class Meta: # type: ignore
        verbose_name = "Время проведения события"
        verbose_name_plural = "Времена проведения события"

    def __repr__(self):
        res = self.start_time.strftime("%H:%M").removeprefix("0")
        if self.end_time:
            res += "-{}".format(self.end_time.strftime("%H:%M"))
        if self.alt_name:
            return f"{self.alt_name}ч. / {res}"
        else:
            return f"{res}"

    def clean(self):
        if self.end_time and self.end_time <= self.start_time:
            raise ValidationError("Время проведения не корректно")


class EventPlace(CommonModel):
    building = models.CharField(blank=True, default="", db_default="", max_length=128, verbose_name="Корпус")
    room = models.CharField(max_length=64, verbose_name="Аудитория")

    class Meta: # type: ignore
        verbose_name = "Место проведения события"
        verbose_name_plural = "Места проведения события"

    def __repr__(self):
        return f"{self.building} {self.room}"

    def get_absolute_url(self):
        return reverse("admin:common_eventplace_change", args=[self.pk])


class EventKind(CommonModel):
    name = models.CharField(verbose_name="Название типа", max_length=64)

    class Meta: # type: ignore
        verbose_name = "Тип события"
        verbose_name_plural = "Типы событий"


    def __repr__(self):
        return str(self.name)


class AbstractDay(CommonModel):
    day_number = models.IntegerField(verbose_name="Смещение от начала повторяющгося фрагмента (пн. первой недели)")
    name = models.CharField(verbose_name="Имя дня в рамках шаблона", max_length=64)

    class Meta: # type: ignore
        verbose_name = "Абстрактный день"
        verbose_name_plural = "Абстрактные дни"


    def __repr__(self):
        return f"{str(self.name)}"


class Organization(CommonModel):
    name = models.CharField(verbose_name="Имя учреждения", max_length=64)

    class Meta: # type: ignore
        verbose_name = "Учреждение"
        verbose_name_plural = "Учреждения"

    def __repr__(self):
        return str(self.name)


class Department(CommonModel):
    name = models.CharField(verbose_name="Имя подразделения", max_length=128)
    shortname = models.CharField(blank=True, null=True, verbose_name="Аббревиатура", max_length=16)
    code = models.CharField(verbose_name="Код подразделения", max_length=16)
    parent_department = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Родительское подразделение"
        )
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, verbose_name="Учреждение")

    class Meta: # type: ignore
        verbose_name = "Подразделение"
        verbose_name_plural = "Подразделения"


    def __repr__(self):
        return str(self.name)


class ScheduleTemplateMetadata(CommonModel):
    class Scope(models.TextChoices):
        BACHELOR = "bachelor", "Бакалавриат"
        MASTER = "master", "Магистратура"
        POSTGRADUATE = "postgraduate", "Аспирантура"
        CONSULTATION = "consultation", "Консультация"

    faculty = models.CharField(max_length=32, verbose_name="Факультет")
    scope = models.CharField(choices=Scope, max_length=32, verbose_name="Обучение")

    class Meta: # type: ignore
        verbose_name = "Метаданные шаблона расписания"
        verbose_name_plural = "Метаданные шаблона расписания"

    def __repr__(self):
        return f"{self.faculty}, {self.Scope(self.scope).label}"


class ScheduleMetadata(CommonModel):
    years = models.CharField(max_length=16, verbose_name="Учебный год")
    course = models.IntegerField(verbose_name="Курс")
    semester = models.IntegerField(verbose_name="Семестр")

    class Meta: # type: ignore
        verbose_name = "Метаданные расписания"
        verbose_name_plural = "Метаданные расписания"

    def __repr__(self):
        return f"{self.years}, {self.course}курс, {self.semester}сем"


class ScheduleTemplate(CommonModel):
    metadata = models.ForeignKey(ScheduleTemplateMetadata, null=True, on_delete=models.PROTECT, verbose_name="Факультет, обучение")
    repetition_period = models.IntegerField(verbose_name="Период повторения в днях")
    repeatable = models.BooleanField(verbose_name="Повторяется ли")
    aligned_by_week_day = models.IntegerField(verbose_name="Выравнивание относительно дня недели (null=0, пн=1, ...)")
    department = models.ForeignKey(Department, null=True, on_delete=models.SET_NULL, verbose_name="Подразделение")

    class Meta: # type: ignore
        verbose_name = "Шаблон расписания"
        verbose_name_plural = "Шаблоны расписаний"


    def __repr__(self):
        if self.repetition_period in [0, 5, 6, 7, 8, 9] or self.repetition_period // 10 == 1:
            return f"{self.department}, каждые {self.repetition_period} дней"

        if self.repetition_period % 10 == 1:
            return f"{self.department}, каждый {self.repetition_period} день"

        if self.repetition_period % 10 in [2, 3, 4]:
            return f"{self.department}, каждые {self.repetition_period} дня"

        return f"{self.department}"

    def save(self, *args, **kwargs):
        super().save(**kwargs)

        from apps.common.selectors import Selector
        from apps.common.services.timetable.read.filters import AbstractEventFilter
        from apps.common.services.timetable.write.factories import rewrite_events

        reader = Selector({"schedule__schedule_template" : self})
        # getting AbstractEvents with existing Events
        reader.add_filter(AbstractEventFilter.with_existing_events())

        reader.find_models(AbstractEvent)

        rewrite_events(reader.get_found_models())


class Schedule(CommonModel):
    class Status(models.IntegerChoices):
        ACTIVE = 0, "Активно"
        DISABLED = 1, "Отключено"
        FUTURE = 2, "Будущее"
        ARCHIVE = 3, "Архивное"

    metadata = models.ForeignKey(ScheduleMetadata, null=True, on_delete=models.PROTECT, verbose_name="Курс, семестр, год")
    status = models.IntegerField(choices=Status, default=0, verbose_name="Текущий статус")
    start_date = models.DateField(null=True, verbose_name="День начала семестра (вкл.)")
    end_date = models.DateField(null=True, verbose_name="День окончания семестра (вкл.)")
    starting_day_number = models.ForeignKey(AbstractDay, null=True, on_delete=models.PROTECT, verbose_name="Номер дня начала первого повторяющегося цикла") 
    schedule_template = models.ForeignKey(ScheduleTemplate, null=True, on_delete=models.PROTECT, verbose_name="Шаблон расписания")

    class Meta: # type: ignore
        verbose_name = "Расписание"
        verbose_name_plural = "Расписания"

    def __repr__(self):
        return f"{self.Status(self.status).label}, {self.schedule_template.metadata}, {self.metadata}"

    def save(self, *args, **kwargs):
        super().save(**kwargs)

        from apps.common.selectors import Selector
        from apps.common.services.timetable.read.filters import AbstractEventFilter
        from apps.common.services.timetable.write.factories import rewrite_events

        reader = Selector({"schedule" : self})
        # getting AbstractEvent with existing Event
        reader.add_filter(AbstractEventFilter.with_existing_events())

        reader.find_models(AbstractEvent)

        rewrite_events(reader.get_found_models())

    def first_event(self):
        events = self.events.all() # type: ignore

        return events.annotate(min_date=models.Min("holdings__date")).order_by("min_date").first() ####

    def last_event(self):
        events = self.events.all() # type: ignore

        return events.annotate(max_date=models.Max("holdings__date")).order_by("-max_date").first()   ######


class EventParticipant(CommonModel):
    class Role(models.TextChoices):
        STUDENT = "student", "Студент"
        TEACHER = "teacher", "Преподаватель"
        ASSISTANT = "assistant", "Ассистент"

    name = models.CharField(max_length=255, verbose_name="Имя")
    role = models.CharField(choices=Role, max_length=48, null=False, verbose_name="Роль")
    is_group = models.BooleanField(verbose_name="Является группой", default=False)
    department = models.ForeignKey(Department, null=True, on_delete=models.SET_NULL, verbose_name="Подразделение")

    class Meta: # type: ignore
        verbose_name = "Участник события"
        verbose_name_plural = "Участники события"

    def __repr__(self):
        return f"{self.name} ({self.role})"

    def get_absolute_url(self):
        return reverse("admin:common_eventparticipant_change", args=[self.pk])


class AbstractEventChanges(CommonModel):
    group = models.TextField(null=True, default="", verbose_name="Группа")
    date_time = models.TextField(null=True, default="", verbose_name="Дата и учебный час")
    subject = models.TextField(null=True, verbose_name="Занятие")
    is_created = models.BooleanField(verbose_name="Запланированное событие создано", default=False)
    is_deleted = models.BooleanField(verbose_name="Запланированное событие удалено", default=False)
    is_exported = models.BooleanField(verbose_name="Запланированное событие экспортировано", default=False)
    origin_teachers = models.TextField(null=True, blank=True, default="", verbose_name="Изначальные участники")
    origin_places = models.TextField(null=True, blank=True, default="", verbose_name="Изначальные места")
    origin_holds_on_date = models.TextField(null=True, blank=True, default="", verbose_name="Изначальные заданный день")
    origin_kind = models.TextField(null=True, blank=True, default="", verbose_name="Изначальный тип")
    final_teachers = models.TextField(null=True, blank=True, default="", verbose_name="Участники после изменений")
    final_places = models.TextField(null=True, blank=True, default="", verbose_name="Места после изменений")
    final_date_time = models.TextField(null=True, blank=True, default="", verbose_name="Дата и учебный час после изменений")
    final_holds_on_date = models.TextField(null=True, blank=True, default="", verbose_name="Заданный день после изменений")
    final_kind = models.TextField(null=True, blank=True, default="", verbose_name="Тип после изменений")

    class Meta: # type: ignore
        verbose_name = "Изменения в запланированном событии"
        verbose_name_plural = "Изменения в запланированных событиях"


    def __repr__(self):
        return f"{self.group}, {self.date_time}, {self.subject}"

    def __str__(self):
        return f"{self.group}, {self.date_time}, {self.subject}"

    def save(self, *args, **kwargs):
        super().save(**kwargs)

        # when logging AbsEvent deleting
        # no need to validate fields
        if self.is_deleted:
            return

        if self.final_teachers and self.origin_teachers == self.final_teachers:
            self.final_teachers = None

        if self.final_places and self.origin_places == self.final_places:
            self.final_places = None

        if self.final_date_time and self.date_time == self.final_date_time:
            self.final_date_time = None

        if self.final_holds_on_date and self.origin_holds_on_date == self.final_holds_on_date:
            self.final_holds_on_date = None

        if self.final_kind and self.origin_holds_on_date == self.final_kind:
            self.final_kind = None

    @staticmethod
    def str_from_participants(participants) -> str:
        """Makes formated str to store from given EventParticipant
        """

        return_value = ""

        for p in participants:
            return_value += f"{p.name}, "
        return_value = return_value[:-2]

        return return_value

    @staticmethod
    def str_from_places(places) -> str:
        """Makes formated str to store from given EventPlace
        """

        return_value = ""

        for p in places:
            return_value += f"{p}, "
        return_value = return_value[:-2]

        return return_value

    @staticmethod
    def str_from_date_time(abstract_event) -> str:
        """Makes formated str to store from given AbstractEvent's day and time_slot
        """

        return f"{abstract_event.abstract_day} / {abstract_event.time_slot.alt_name}ч."

    def initialize(self, ae):
        """Fills model with origin values from given AbstractEvent
        """

        self.group = self.str_from_participants(ae.get_groups())
        self.date_time = self.str_from_date_time(ae)
        self.subject = ae.subject.name
        self.origin_teachers = self.str_from_participants(ae.get_teachers())
        self.origin_places = self.str_from_places(ae.places.all())
        self.origin_holds_on_date = ae.holds_on_date
        self.origin_kind = ae.kind.name if ae.kind else ""

    def get_export_data(self) -> list[list[str]]:
        """Prepare stored data to export
        """

        export_data_base = [self.datemodified.strftime('%Y-%m-%d %H:%M:%S'), self.group, self.date_time, self.subject]
        export_data = []

        if self.is_deleted:
            export_data.append([*export_data_base, "УДАЛЕНО"])
        else:
            if self.is_created:
                export_data.append([*export_data_base, "СОЗДАНО"])

            if self.final_teachers:
                export_data.append([*export_data_base, "ПРЕПОДАВАТЕЛЬ", self.origin_teachers, self.final_teachers])

            if self.final_places:
                export_data.append([*export_data_base, "АУДИТОРИЯ", self.origin_places, self.final_places])

            if self.final_date_time:
                export_data.append([*export_data_base, "ДЕНЬ НЕДЕЛИ/УЧ. ЧАС", self.date_time, self.final_date_time])

            if self.final_holds_on_date:
                export_data.append([*export_data_base, "ЯВНАЯ ДАТА", self.origin_holds_on_date, self.final_holds_on_date])

            if self.final_kind:
                export_data.append([*export_data_base, "ТИП", self.origin_kind, self.final_kind])

        self.is_exported = True

        self.save()

        self.clear_relation_with_abs_event()

        return export_data

    def clear_relation_with_abs_event(self) -> None:
        """Removes all references to self from related AbstractEvents
        """

        for ae in AbstractEvent.objects.filter(changes=self):
            ae.changes = None

            ae.save()


class AbstractEvent(CommonModel):
    kind = models.ForeignKey(EventKind, null=True, blank=True, default=None, on_delete=models.PROTECT, verbose_name="Тип")
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, verbose_name="Предмет")
    participants = models.ManyToManyField(EventParticipant, verbose_name="Участники")
    places = models.ManyToManyField(EventPlace, verbose_name="Места")
    abstract_day = models.ForeignKey(AbstractDay, on_delete=models.PROTECT, verbose_name="Абстрактный день")
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.PROTECT, verbose_name="Временной интервал") # null=True, blank=True
    # for many dates should create many AbstractEvents
    holds_on_date = models.DateField(null=True, blank=True, verbose_name="Проводится только в заданный день")
    schedule = models.ForeignKey(Schedule, null=True, on_delete=models.CASCADE, related_name="events", verbose_name="Расписание")
    changes = models.ForeignKey(AbstractEventChanges, null=True, blank=True, on_delete=models.SET_NULL, editable=False, verbose_name="Изменения")

    class Meta: # type: ignore
        verbose_name = "Запланированное событие"
        verbose_name_plural = "Запланированные события"

    def __repr__(self):
        return f"Занятие по {self.subject.name}, {self.time_slot.alt_name}ч."

    def save(self, *args, **kwargs):
        super().save(**kwargs)

        from apps.common.services.timetable.write.factories import (
            refresh_related_events,
        )

        # Calling here because need updated AbstractEvent reference inside Events
        refresh_related_events(self, update_m2m=False)

    @property
    def department(self):
        """Returns Event Department
        """
        return self.schedule.schedule_template.department

    def get_groups(self):
        """Filter and returns groups from participants 
        """
        return self.participants.filter(is_group=True)

    def get_teachers(self):
        """Filter and returns teachers from participants 
        """
        return self.participants.filter(role__in=[EventParticipant.Role.TEACHER, EventParticipant.Role.ASSISTANT])
    
    def get_absolute_url(self):
        return reverse("admin:common_abstractevent_change", args=[self.pk])

    def generate_changes_on_creating(self):
        """Create AbstractEventChange model

        Should be called when AbstractEvent model creates

        Not saving self instance on complete
        """

        changes = AbstractEventChanges()

        changes.date_time = AbstractEventChanges.str_from_date_time(self)
        changes.subject = self.subject.name
        changes.is_created = True

        if self.holds_on_date:
            changes.final_holds_on_date = self.holds_on_date

        changes.final_kind = self.kind.name if self.kind else ""

        changes.save()

        self.changes = changes

    def update_change_model(self):
        """Writes AbsractEvent changes into AbstractEventChange model

        If no changes done do nothing. Looking for only non m2m fields

        Not saving self instance on complete
        """

        previous_ae = AbstractEvent.objects.get(pk=self.pk)

        is_date_time_changed = previous_ae.abstract_day != self.abstract_day or previous_ae.time_slot != self.time_slot
        is_holds_on_date_changed = previous_ae.holds_on_date != self.holds_on_date
        is_kind_changed = previous_ae.kind != self.kind

        # continue only if something changed
        if not is_date_time_changed and not is_holds_on_date_changed and not is_kind_changed:
            return

        changes = previous_ae.changes

        if not changes:
            changes = AbstractEventChanges()

            changes.initialize(previous_ae)

        if is_date_time_changed:
            changes.final_date_time = AbstractEventChanges.str_from_date_time(self)

        if is_holds_on_date_changed:
            changes.final_holds_on_date = self.holds_on_date

        if is_kind_changed:
            changes.final_kind = self.kind.name if self.kind else ""

        changes.save()

        self.changes = changes


class EventCancel(CommonModel):
    class Meta: # type: ignore
        verbose_name = "Отмена событий"
        verbose_name_plural = "Отмены событий"

    date = models.DateField(blank=False, verbose_name="Отменить для даты")
    department = models.ForeignKey(Department, on_delete=models.CASCADE, verbose_name="Подразделение")

    def __repr__(self):
        return f"Отмена событий на {self.date}"

    def save(self, *args, **kwargs):
        super().save(**kwargs)

        from apps.common.selectors import Selector
        from apps.common.services.timetable.read.filters import (
            DateFilter,
            EventFilter,
        )
        from apps.common.services.timetable.write.factories import apply_event_cancel

        reader = Selector(DateFilter.from_singe_date(self.date))
        reader.add_filter(EventFilter.by_department(self.department))

        reader.find_models(Event)

        for e in reader.get_found_models():
            apply_event_cancel(self, e)


class DayDateOverride(CommonModel):
    day_source = models.DateField(blank=False, verbose_name="Перенести с даты")
    day_destination = models.DateField(blank=False, verbose_name="Перенести на дату")
    department = models.ForeignKey(Department, null=True, on_delete=models.CASCADE, verbose_name="Подразделение")

    class Meta: # type: ignore
        verbose_name = "Перенос дня на другую дату"
        verbose_name_plural = "Переносы дней на другие даты"

    def __repr__(self):
        return f"Перенос с {self.day_source} на {self.day_destination}"

    def save(self, *args, **kwargs):
        super().save(**kwargs)

        from apps.common.selectors import Selector
        from apps.common.services.timetable.read.filters import (
            DateFilter,
            EventFilter,
        )
        from apps.common.services.timetable.write.factories import (
            apply_day_date_override,
        )

        reader = Selector(DateFilter.from_singe_date(self.day_source))
        reader.add_filter(EventFilter.by_department(self.department))

        reader.find_models(Event)

        for e in reader.get_found_models():
            apply_day_date_override(self, e)


class Event(CommonModel):
    date = models.DateField(null=True, blank=False, verbose_name="Дата")
    date_override = models.ForeignKey(DayDateOverride, null=True, blank=True, editable=False, on_delete=models.SET_NULL, verbose_name="Перенос дня")
    kind_override = models.ForeignKey(EventKind, null=True, blank=True, default=None, on_delete=models.PROTECT, verbose_name="Тип")
    subject_override = models.ForeignKey(Subject, null=True, on_delete=models.PROTECT, verbose_name="Предмет")
    participants_override = models.ManyToManyField(EventParticipant, verbose_name="Участники")
    places_override = models.ManyToManyField(EventPlace, verbose_name="Места")
    time_slot_override = models.ForeignKey(TimeSlot, null=True, on_delete=models.PROTECT, verbose_name="Временной интервал")
    abstract_event = models.ForeignKey(AbstractEvent, null=True, editable=False, on_delete=models.CASCADE, verbose_name="Запланированное событие")
    is_event_canceled = models.BooleanField(verbose_name="Событие отменено", default=False)
    event_cancel = models.ForeignKey(EventCancel, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Отмена события")
    is_event_overriden = models.BooleanField(verbose_name="Событие изменено вручную", default=False)

    class Meta: # type: ignore
        verbose_name = "Событие"
        verbose_name_plural = "События"

    def __repr__(self):
        return f"Занятие по {self.abstract_event.subject.name}"

    @property
    def department(self):
        return self.abstract_event.schedule.schedule_template.department

    def get_groups(self):
        return self.participants_override.filter(is_group=True)

    def get_teachers(self):
        return self.participants_override.filter(role__in=[EventParticipant.Role.TEACHER, EventParticipant.Role.ASSISTANT])

    def check_date_interactions(self):
        """Checks Event date and attaching/detaching DayDateOverride if needed
        """

        if not self.date_override:
            from apps.common.selectors import Selector
            from apps.common.services.timetable.write.factories import (
                apply_day_date_override,
            )

            reader = Selector({"day_source" : self.date})
            reader.add_filter({"department" : self.department})

            reader.find_models(DayDateOverride)

            if reader.get_found_models().exists():
                apply_day_date_override(reader.get_found_models().first(), self, call_save_method=False)

            return

        # if destination date from attached DayDateOverride
        # differ from Event date
        if self.date_override.day_destination != self.date:
            # need detach DayDateOverride from Event
            self.date_override = None

    def check_canceling(self):
        """Checks Event date and attaching/detaching EventCancel if needed
        """

        # skip manualy canceled events
        if self.is_event_canceled and not self.event_cancel:
            return

        from apps.common.selectors import Selector
        from apps.common.services.timetable.read.filters import DateFilter
        from apps.common.services.timetable.write.factories import apply_event_cancel

        reader = Selector({"department" : self.department})
        reader.add_filter(DateFilter.from_singe_date(self.date))

        reader.find_models(EventCancel)

        if reader.get_found_models().exists():
            apply_event_cancel(reader.get_found_models().first(), self, False)
        else:
            self.is_event_canceled = False
            self.event_cancel = None
