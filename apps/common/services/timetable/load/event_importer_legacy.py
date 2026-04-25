import json
import re
from datetime import date, datetime

from apps.common.models import (
    AbstractDay,
    EventKind,
    EventParticipant,
    EventPlace,
    Schedule,
    Subject,
    TimeSlot,
)
from apps.common.services.timetable.read.filters import TimeSlotFilter
from apps.common.services.timetable.utilities.model_helpers import (
    is_abstract_event_already_exists,
)
from apps.common.services.timetable.utilities.normalizers import (
    normalize_kind_name,
    normalize_participant_name,
    normalize_place_building_and_room,
    normalize_scope,
    normalize_subject_name,
    normalize_time_slot_display_name,
)
from apps.common.services.timetable.utilities.utilities import (
    get_number_from_month_name,
    get_scope_from_label,
    replace_roman_with_arabic_numerals,
)
from apps.common.services.timetable.write.factories import (
    create_abstract_event,
    fill_semester_for_dates,
)


class EventImporterLegacy:
    SUBJECT_NORMALIZATION_CAPITALIZE = False

    @classmethod
    def _collect_reference_data(cls, entries) -> dict:
        """Collects data from all entries in imported JSON
        """
        
        subjects : set[str] = set()
        kinds : set[str] = set()
        teacher_names : set[str] = set()
        group_names : set[str] = set()
        places : set[tuple[str, str]] = set()
        time_slots : set[str] = set()

        for entry in entries:
            subjects.add(normalize_subject_name(entry["subject"]))
            kinds.add(normalize_kind_name(entry["kind"]))

            for teacher_name in entry.get("participants", {}).get("teachers", []):
                normalized_teacher_name = normalize_participant_name(teacher_name)

                if normalized_teacher_name:
                    teacher_names.add(normalized_teacher_name)

            for group_name in entry.get("participants", {}).get("student_groups", []):
                normalized_group_name = normalize_participant_name(group_name)

                if normalized_group_name:
                    group_names.add(normalized_group_name)

            for place_repr in entry.get("places", []):
                normalized_place = normalize_place_building_and_room(place_repr)

                if normalized_place:
                    places.add(normalized_place)

            for time_slot_repr in entry.get("hours", []):
                normalized_time_slot = normalize_time_slot_display_name(time_slot_repr)

                if normalized_time_slot:
                    time_slots.add(normalized_time_slot)


        return {
            "subjects" : subjects,
            "kinds" : kinds,
            "teacher_names" : teacher_names,
            "group_names" : group_names,
            "places" : places,
            "time_slots" : time_slots
        }

    @classmethod
    def _ensure_reference_data(cls, reference_data : dict) -> None:
        """Creates models for non-existing inside database JSON data
        """

        if not reference_data:
            return

        subjects = reference_data.get("subjects", set())
        if subjects:
            existing_subjects = set(
                Subject.objects.filter(name__in=subjects).values_list("name", flat=True)
            )
            new_subjects = [
                Subject(name=name)
                for name in subjects
                if name not in existing_subjects
            ]
            if new_subjects:
                Subject.objects.bulk_create(new_subjects)

        kinds = reference_data.get("kinds", set())
        if kinds:
            existing_kinds = set(
                EventKind.objects.filter(name__in=kinds).values_list("name", flat=True)
            )
            new_kinds = [
                EventKind(name=name)
                for name in kinds
                if name not in existing_kinds
            ]
            if new_kinds:
                EventKind.objects.bulk_create(new_kinds)

        teacher_names = reference_data.get("teacher_names", set())
        group_names = reference_data.get("group_names", set())
        all_participant_names = teacher_names | group_names

        if all_participant_names:
            existing_participants = set(
                EventParticipant.objects.filter(name__in=all_participant_names).values_list("name", flat=True)
            )
            new_participants: list[EventParticipant] = []

            for name in teacher_names:
                if name in existing_participants:
                    continue
                new_participants.append(
                    EventParticipant(
                        name=name,
                        role=EventParticipant.Role.TEACHER,
                        is_group=False,
                        # TODO: add department
                    )
                )

            for name in group_names:
                if name in existing_participants:
                    continue
                new_participants.append(
                    EventParticipant(
                        name=name,
                        role=EventParticipant.Role.STUDENT,
                        is_group=True,
                        # TODO: add department
                    )
                )

            if new_participants:
                EventParticipant.objects.bulk_create(new_participants)

        places = reference_data.get("places", set())
        if places:
            rooms = {room for _, room in places}

            if rooms:
                existing_places = set(
                    EventPlace.objects.filter(room__in=rooms).values_list("building", "room")
                )
            else:
                existing_places = set()

            new_places = [
                EventPlace(building=building, room=room)
                for building, room in places
                if (building, room) not in existing_places
            ]

            if new_places:
                EventPlace.objects.bulk_create(new_places)

        #TODO: rewrite
        time_slots = reference_data.get("time_slots", set())
        if time_slots:
            filter_by_start_time, left_time_slots = TimeSlotFilter.by_start_time([time_slot[1] for time_slot in time_slots])
            
            if filter_by_start_time:
                existing_time_slots = set(
                    TimeSlot.objects.filter(**filter_by_start_time).values_list("start_time", flat=True)
                )
            else:
                existing_time_slots = set()

            # At this moment, we not auto creating TimeSlots from alt_names
            """
            if left_time_slots:
                filter_by_alt_name, _ = TimeSlotFilter.by_alt_name(left_time_slots)

                if filter_by_alt_name:
                    existing_time_slots.update(set(
                        TimeSlot.objects.filter(**filter_by_alt_name).values_list("alt_name", "start_time")
                    ))
            """
            
            new_time_slots = [
                TimeSlot(
                    alt_name=alt_name, 
                    start_time=datetime.strptime(start_time, "%H:%M"), 
                    end_time=datetime.strptime(end_time, "%H:%M") if end_time else None
                )
                for alt_name, start_time, end_time in time_slots
                if start_time and datetime.strptime(start_time, "%H:%M").time() not in existing_time_slots
            ]

            if new_time_slots:
                TimeSlot.objects.bulk_create(new_time_slots)

    @classmethod
    def import_event_data(cls, event_data : str):
        """Reads data from given file and fill database with new AbstractEvents and Events
        """
        
        json_data = json.loads(event_data)
        
        cls.make_event_import(
            json_data["title"],
            json_data["table"]["grid"],
            json_data["table"]["datetime"]["weeks"],
            json_data["table"]["datetime"]["week_days"],
            json_data["table"]["datetime"]["months"]
        )
    
    @classmethod
    def make_event_import(cls, title : str, entries, weeks, week_days : list[str], months : list[str]):
        """Applies data from loaded JSON on database
        """
        
        schedule = cls.find_schedule(replace_roman_with_arabic_numerals(title))
        reference_data = cls._collect_reference_data(entries)
        cls._ensure_reference_data(reference_data)
        reference_lookup = cls._build_reference_lookup(reference_data)
        global_calendar = cls.make_calendar(weeks, months, schedule)

        for entry in entries:
            cls.create_events(*cls.parse_data(entry, global_calendar, week_days, reference_lookup), schedule)
        
    @classmethod
    def make_calendar(cls, weeks, months : list[str], schedule : Schedule) -> dict:
        """
        
        parsed_weeks = { 
            week_id : { 
                week_day_index : [
                    dd.mm.YYYY,
                    dd.mm.YYYY...
                ]
            } 
        }

        Example:

        parsed_weeks = { 
            "first_week" : { 
                0 : [
                    1.02.2025,
                    15.02.2025
                ],
                1 : [
                    2.02.2025,
                    16.02.2025
                ]
            },
            "second_week" : { 
                0 : [
                    8.02.2025,
                    22.02.2025
                ],
                1 : [
                    9.02.2025,
                    23.02.2025
                ]
            } 
        }
        """

        normalized_weeks = {}
        if isinstance(weeks, dict):
            normalized_weeks = weeks
        elif isinstance(weeks, list):
            for week_entry in weeks:
                if isinstance(week_entry, dict):
                    for week_key, data in week_entry.items():
                        normalized_weeks[week_key] = data
        else:
            raise ValueError("Некорректный формат данных недель в JSON.")

        calendar = {}
        # TODO: test with second semester schedule
        LEFT_YEAR, RIGHT_YEAR = schedule.metadata.years.split("-", 1)

        for week_id in normalized_weeks.keys():
            calendar[week_id] = {}

            for week_day in normalized_weeks[week_id]:
                calendar[week_id][week_day["week_day_index"]] = []

                for month in week_day["calendar"]:
                    month_number = get_number_from_month_name(months[month["month_index"]])

                    for month_day in month["month_days"]:
                        calendar[week_id][week_day["week_day_index"]].append(
                            datetime.strptime(
                                "{}.{}.{}".format(month_day, month_number, LEFT_YEAR if month_number > 6 else RIGHT_YEAR), 
                                "%d.%m.%Y"
                            ).date()
                        )

        return calendar

    @classmethod
    def _build_reference_lookup(cls, ref_data: dict) -> dict:
        reference_lookup = {
            "subjects" : {},
            "kinds" : {},
            "participants" : {},
            "places" : {},
            "time_slots" : TimeSlot.objects.none()
        }

        subjects = ref_data.get("subjects", set())
        if subjects:
            subject_qs = Subject.objects.filter(name__in=list(subjects))
            reference_lookup["subjects"] = {}
            for subject in subject_qs:
                reference_lookup["subjects"].setdefault(subject.name, subject)

        kinds = ref_data.get("kinds", set())
        if kinds:
            kind_qs = EventKind.objects.filter(name__in=list(kinds))
            reference_lookup["kinds"] = {}
            for kind in kind_qs:
                reference_lookup["kinds"].setdefault(kind.name, kind)

        all_participants = ref_data.get("teacher_names", set()) | ref_data.get("group_names", set())
        if all_participants:
            participants_qs = EventParticipant.objects.filter(name__in=list(all_participants))
            reference_lookup["participants"] = {}
            for participant in participants_qs:
                reference_lookup["participants"].setdefault(participant.name, participant)

        places = ref_data.get("places", set())
        if places:
            rooms = {room for _, room in places}

            if rooms:
                place_queryset = EventPlace.objects.filter(room__in=rooms)

                reference_lookup["places"] = {
                    (place.building, place.room) : place for place in place_queryset
                }

        time_slots = ref_data.get("time_slots", set())
        if time_slots:
            start_times = {start_time for _, start_time, _ in time_slots if start_time}
            alt_names = {alt_name for alt_name, start_time, _ in time_slots if not start_time}

                        
            if start_times:
                reference_lookup["time_slots"] = TimeSlot.objects.filter(start_time__in=start_times)

            if alt_names:
                reference_lookup["time_slots"] |= TimeSlot.objects.filter(alt_name__in=alt_names)

            # reference_lookup["time_slots"].update({
            #     (
            #         time_slot.alt_name, 
            #         time_slot.start_time.strftime("%H:%M").removeprefix("0"), 
            #         time_slot.end_time.strftime("%H:%M").removeprefix("0") if time_slot.end_time else ""
            #     ) : time_slot for time_slot in time_slot_queryset_from_start_times | time_slot_queryset_from_alt_names
            # })

        return reference_lookup

    @classmethod
    def parse_data(cls, entry, global_calendar, week_days : list[str], reference_lookup : dict):
        """Finds existing models for JSON data

        Method uses pre-prepared reference data
        """

        week_id = entry["week"]
        week_day_index = entry["week_day_index"]

        kind_name = normalize_kind_name(entry["kind"])
        kind = reference_lookup["kinds"].get(kind_name)
        if kind is None:
            raise EventKind.DoesNotExist(f"Тип события '{kind_name}' не найден после подготовки справочников.")

        subject_name = normalize_subject_name(entry["subject"])
        subject = reference_lookup["subjects"].get(subject_name)
        if subject is None:
            raise Subject.DoesNotExist(f"Предмет '{subject_name}' не найден после подготовки справочников.")

        participants = []
        missing_participants = []

        for teacher_name in entry.get("participants", {}).get("teachers", []):
            normalized = normalize_participant_name(teacher_name)
            participant = reference_lookup["participants"].get(normalized)
            if participant:
                participants.append(participant)
            else:
                missing_participants.append(normalized)

        for group_name in entry.get("participants", {}).get("student_groups", []):
            normalized = normalize_participant_name(group_name)
            participant = reference_lookup["participants"].get(normalized)
            if participant:
                participants.append(participant)
            else:
                missing_participants.append(normalized)

        if missing_participants:
            raise EventParticipant.DoesNotExist(
                f"Не удалось найти участников: {', '.join(missing_participants)}"
            )

        places = []
        missing_places = []
        for place_repr in entry.get("places", []):
            normalized_place = normalize_place_building_and_room(place_repr)

            if not normalized_place:
                continue

            place = reference_lookup["places"].get(normalized_place)
            if place:
                places.append(place)
            else:
                missing_places.append(place_repr)

        if missing_places:
            raise EventPlace.DoesNotExist(
                f"Не удалось найти аудитории: {', '.join(missing_places)}"
            )

        abstract_day = AbstractDay.objects.get(
            name__startswith=1 if week_id == "first_week" else 2,
            name__endswith=week_days[week_day_index].capitalize()
        )

        time_slots = []
        missing_time_slots = []
        for time_slot_repr in entry.get('hours', []):
            normalized_time_slot = normalize_time_slot_display_name(time_slot_repr)

            if not normalized_time_slot:
                continue
            
            ## TODO: select timeslot with alt_name > without altname
            time_slot = reference_lookup["time_slots"].filter(
                **TimeSlotFilter.from_display_name(normalized_time_slot[1] if normalized_time_slot[1] else normalized_time_slot[0])
            ).first()

            if time_slot:
                time_slots.append(time_slot)
            else:
                missing_time_slots.append(time_slot_repr)

        if missing_time_slots:
            raise TimeSlot.DoesNotExist(
                f"Не найден учебный час для значений: {', '.join(missing_time_slots)}"
            )
        
        holds_on_date_values = entry.get("holds_on_date") or []
        if holds_on_date_values:
            holds_on_dates = []

            for date_ in holds_on_date_values:
                holds_on_dates.append(datetime.strptime(date_, "%d.%m.%Y").date())
        else:
            holds_on_dates = [ None ]

        calendar = global_calendar[week_id][week_day_index]

        return kind, subject, participants, places, abstract_day, time_slots, holds_on_dates, calendar
  
    @staticmethod
    def create_events(kind : EventKind, 
                        subject : Subject,
                        participants : list[EventParticipant],
                        places : list[EventPlace],
                        abstract_day : AbstractDay,
                        time_slots : list[TimeSlot],
                        holds_on_dates : list[date]|list[None],
                        calendar : dict,
                        schedule : Schedule):
        """Creates AbstractEvents and Events for given TimeSlots and dates

        Not create duplicates
        """

        for date_ in holds_on_dates:
            for time_slot in time_slots:
                if is_abstract_event_already_exists(
                    kind, subject, participants, places, abstract_day, time_slot, date_, schedule
                ):
                    continue

                created_abstract_event = create_abstract_event(
                    kind,
                    subject,
                    participants,
                    places,
                    abstract_day,
                    time_slot,
                    date_,
                    schedule
                )

                fill_semester_for_dates(created_abstract_event, calendar)
        
    ## TODO: write tests
    @staticmethod
    def find_schedule(title : str) -> Schedule:
        """Parse timetable title and find Schedule based on this title

        Schedule must already exist. 
        Title must contain course, faculty, semester and years information

        Returns found Schedule

        Returns:
            schedule
        """
        
        # 4 курса
        # 4 курс
        # 4курса
        # 4   курса
        # 1ый курс
        # 5-ого курса
        # 3-го курса
        COURSE_REG_EX = r"(\d)(\-?[а-яА-ЯёЁ]*)?\s*курса?"

        # ФЭВТ
        # ТК
        # курсФЭВТна
        # TODO: ФАСТиВ
        FACULTY_REG_EX = r"[А-ЯЁ]{2,}"

        # 2 семестр
        # 2семестр
        # 2   семестр
        # 2-ой семестр
        # 2-й семестр
        # 1ый семестр
        SEMESTER_REG_EX = r"(\d)(\-?[а-яА-ЯёЁ]*)?\s*семестра?"

        # 2024-2025
        # 2024 -  2025
        FULL_YEARS_REG_EX = r"(\d{4}\s*-\s*\d{4})"

        # Бакалавры
        # бакалавриат
        # магистратура
        # Аспирантура
        # консульт.
        SCOPE_REG_EX = r"(([бБ]акалавр|[мМ]агистр|[аА]спирант|[кК]онсульт)[а-яА-ЯёЁ]*)"

        filter_query = {}

        course_match = re.search(COURSE_REG_EX, title, flags=re.IGNORECASE)
        if course_match:
            filter_query["metadata__course"] = int(course_match.group(1))

        faculty_tokens = re.findall(FACULTY_REG_EX, title)
        if faculty_tokens:
            filter_query["schedule_template__metadata__faculty__iexact"] = faculty_tokens[-1]

        semester_match = re.search(SEMESTER_REG_EX, title, flags=re.IGNORECASE)
        if semester_match:
            filter_query["metadata__semester"] = int(semester_match.group(1))

        years_match = re.search(FULL_YEARS_REG_EX, title)
        if years_match:
            filter_query["metadata__years"] = years_match.group(1).replace(" ", "")

        scope_match = re.search(SCOPE_REG_EX, title)
        if scope_match:
            filter_query["schedule_template__metadata__scope"] = get_scope_from_label(
                normalize_scope(scope_match.group(1))
            )

        if not filter_query:
            raise ValueError(
                f"Не удалось извлечь параметры расписания из заголовка '{title}'. "
                "Убедитесь, что он содержит хотя бы номер курса и сокращение факультета."
            )
        
        filter_query["status"] = Schedule.Status.ACTIVE

        schedules = Schedule.objects.filter(**filter_query)

        if not schedules.exists():
            raise Schedule.DoesNotExist(
                f"Расписание с параметрами {filter_query} не найдено. "
                f"Заголовок: '{title}'."
            )

        if schedules.count() > 1:
            raise Schedule.MultipleObjectsReturned(
                f"Найдено несколько расписаний, удовлетворяющих параметрам {filter_query}. "
                "Уточните заголовок или дополните его семестром и учебным годом."
            )

        return schedules.first()