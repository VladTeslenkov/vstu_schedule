import json
from datetime import datetime

from apps.common.models import (
    AbstractDay,
    Department,
    EventParticipant,
    EventPlace,
    Organization,
    Schedule,
    ScheduleMetadata,
    ScheduleTemplate,
    ScheduleTemplateMetadata,
    Subject,
)
from apps.common.services.timetable.utilities.model_helpers import (
    is_department_already_exists,
    is_participant_already_exists,
    is_place_already_exists,
    is_subject_already_exists,
)
from apps.common.services.timetable.utilities.normalizers import (
    format_participant_name,
    normalize_place_building_and_room,
)
from apps.common.services.timetable.utilities.utilities import (
    get_scope_from_label,
)


class ReferenceImporter:
    @staticmethod
    def import_place_reference(reference_data : str):
        """

        Not create duplicates
        """

        json_data = json.loads(reference_data)

        places_to_create = []
        already_read_places = []

        for place in json_data["places"]:
            normalized_place = normalize_place_building_and_room(place)

            if normalized_place in already_read_places or is_place_already_exists(*normalized_place):
                continue

            places_to_create.append(
                EventPlace(
                    building=normalized_place[0],
                    room=normalized_place[1]
                )
            )

            already_read_places.append(normalized_place)

        if places_to_create:
            EventPlace.objects.bulk_create(places_to_create)

    @staticmethod
    def import_subject_reference(reference_data : str):
        """

        Not create duplicates
        """

        json_data = json.loads(reference_data)

        subjects_to_create = []
        already_read_subjects = []

        for entry in json_data:
            subject = entry["discipline_name"]

            if subject in already_read_subjects or is_subject_already_exists(subject):
                continue

            subjects_to_create.append(
                Subject(name=subject)
            )

            already_read_subjects.append(subject)

        if subjects_to_create:
            Subject.objects.bulk_create(subjects_to_create)

    @staticmethod
    def import_faculty_reference(reference_data : str):
        """

        Not create duplicates
        """

        json_data = json.loads(reference_data)

        # TODO: looking baad
        organization = Organization.objects.get(name="ВолгГТУ")
        faculties_to_create = []
        already_read_faculties = []

        for entry in json_data:
            department_name = entry["faculty_fullname"]
            department_shortname = entry["faculty_shortname"]
            department_code = entry["faculty_id"]

            if (department_name, department_shortname, department_code) in already_read_faculties \
                or is_department_already_exists(department_name, department_shortname, department_code):
                continue

            faculties_to_create.append(
                Department(
                    name=department_name,
                    shortname=department_shortname,
                    code=department_code,
                    parent_department=None,
                    organization=organization
                )
            )

            already_read_faculties.append((department_name, department_shortname, department_code))

        if faculties_to_create:
            Department.objects.bulk_create(faculties_to_create)

    @staticmethod
    def import_department_reference(reference_data : str):
        """

        Creates Department even parent_department not found

        Not create duplicates
        """

        json_data = json.loads(reference_data)

        # TODO: looking baad
        organization = Organization.objects.get(name="ВолгГТУ")
        departments_to_create = []
        already_read_departments = []

        for entry in json_data:
            department_name = entry["department_fullname"]
            department_shortname = entry["department_shortname"]
            department_code = entry["department_code"]

            if (department_name, department_shortname, department_code) in already_read_departments \
                or is_department_already_exists(department_name, department_shortname, department_code):
                continue

            try:
                parent_department = Department.objects.get(code=entry["faculty_id"])
            except Department.DoesNotExist:
                parent_department = None

            departments_to_create.append(
                Department(
                    name=department_name,
                    shortname=department_shortname,
                    code=department_code,
                    parent_department=parent_department,
                    organization=organization
                )
            )

            already_read_departments.append((department_name, department_shortname, department_code))

        if departments_to_create:
            Department.objects.bulk_create(departments_to_create)

    @staticmethod
    def import_teacher_reference(reference_data : str):
        """

        Creates EventParticipant (teacher) even Department not found

        Can create duplicates when teachers have same names (surname and name, patronymic abbreviations)
        """

        json_data = json.loads(reference_data)

        teachers_to_create = []

        for entry in json_data:
            try:
                department = Department.objects.get(code=entry["staff_department_code"])
            except Department.DoesNotExist:
                department = None

            teachers_to_create.append(
                EventParticipant(
                    name=format_participant_name(
                        entry["staff_surname"], 
                        entry["staff_name"], 
                        entry["staff_patronymic"]
                    ),
                    role=EventParticipant.Role.TEACHER, ## TODO: assistant
                    is_group=False,
                    department=department
                )
            )

        if teachers_to_create:
            EventParticipant.objects.bulk_create(teachers_to_create)

    @staticmethod
    def import_student_reference(reference_data : str):
        """

        Creates EventParticipant (student) even Department not found

        Not create duplicates
        """

        json_data = json.loads(reference_data)

        students_to_create = []
        already_read_students = []

        for entry in json_data:
            try:
                department = Department.objects.get(code=entry["faculty_id"])
            except Department.DoesNotExist:
                department = None

            student_name = entry["group_name"]

            if student_name in already_read_students or is_participant_already_exists(student_name, department):
                continue

            students_to_create.append(
                EventParticipant(
                    name=student_name,
                    role=EventParticipant.Role.STUDENT,
                    is_group=True,
                    department=department
                )
            )
            already_read_students.append(student_name)

        if students_to_create:
            EventParticipant.objects.bulk_create(students_to_create)

    @staticmethod
    def import_schedule(reference_data : str, save_archive_schedules : bool):
        json_data = json.loads(reference_data)

        for entry in json_data:
            scope_value = get_scope_from_label(entry["scope"])

            if not scope_value:
                raise ValueError(f"Степень обучения '{entry["scope"]}' не найдена.")

            try:
                schedule_template_metadata = ScheduleTemplateMetadata.objects.get(
                    faculty=entry["schedule_template_metadata_faculty_shortname"],
                    scope=scope_value
                )
            except ScheduleTemplateMetadata.DoesNotExist:
                schedule_template_metadata = ScheduleTemplateMetadata.objects.create(
                    faculty=entry["schedule_template_metadata_faculty_shortname"],
                    scope=scope_value
                )

            try:
                department_ = Department.objects.get(shortname=entry["department_shortname"])
            except Department.DoesNotExist:
                raise Department.DoesNotExist(f"Подразделение '{entry["department_shortname"]}' не найдено.")

            try:
                schedule_template = ScheduleTemplate.objects.get(
                    metadata=schedule_template_metadata,
                    department=department_
                )
            except ScheduleTemplate.DoesNotExist:
                schedule_template = ScheduleTemplate.objects.create(
                    metadata=schedule_template_metadata,
                    repetition_period=14,
                    repeatable=True,
                    aligned_by_week_day=1,
                    department=department_
                )

            try:
                schedule_metadata = ScheduleMetadata.objects.get(
                    years=entry["years"],
                    course=entry["course"],
                    semester=entry["semester"]
                )
            except ScheduleMetadata.DoesNotExist:
                schedule_metadata = ScheduleMetadata.objects.create(
                    years=entry["years"],
                    course=entry["course"],
                    semester=entry["semester"]
                )

            try:
                if not save_archive_schedules:
                    Schedule.objects.filter(
                        metadata=schedule_metadata,
                        schedule_template=schedule_template,
                        status=Schedule.Status.ARCHIVE
                    ).delete()
            except Schedule.DoesNotExist:
                pass

            try:
                existing_schedule = Schedule.objects.get(
                    metadata=schedule_metadata,
                    schedule_template=schedule_template,
                    status=Schedule.Status.ACTIVE
                )

                existing_schedule.status = Schedule.Status.ARCHIVE
                existing_schedule.save()
            except Schedule.DoesNotExist:
                pass

            Schedule.objects.create(
                metadata=schedule_metadata,
                status=Schedule.Status.ACTIVE,
                start_date=datetime.strptime(entry["start_date"], "%d.%m.%Y"),
                end_date=datetime.strptime(entry["end_date"], "%d.%m.%Y"),
                starting_day_number=AbstractDay.objects.get(day_number=0),
                schedule_template=schedule_template
            )
