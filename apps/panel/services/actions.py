from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from apps.common.models import Organization, Schedule
from apps.common.services.timetable.load.event_importer import EventImporter
from apps.common.services.timetable.load.reference_importer import ReferenceImporter
from apps.common.services.timetable.utilities.model_helpers import (
    create_common_abstract_days,
    create_common_time_slots,
)

ActionKind = Literal["file", "button"]


@dataclass(frozen=True)
class PanelAction:
    action_id: str
    title: str
    description: str
    kind: ActionKind
    button_label: str
    file_field: str = "upload"
    mode_field: str = ""
    mode_choices: tuple[tuple[str, str], ...] = ()


PANEL_ACTIONS: tuple[PanelAction, ...] = (
    PanelAction(
        "import_subject_reference",
        "Импорт справочника дисциплин",
        "Загружает справочник дисциплин из файла.",
        "file",
        "Импортировать",
    ),
    PanelAction(
        "import_teacher_reference",
        "Импорт справочника преподавателей",
        "Загружает справочник преподавателей из файла.",
        "file",
        "Импортировать",
    ),
    PanelAction(
        "import_student_reference",
        "Импорт справочника групп",
        "Загружает справочник студенческих групп из файла.",
        "file",
        "Импортировать",
    ),
    PanelAction(
        "import_place_reference",
        "Импорт справочника аудиторий",
        "Загружает справочник аудиторий из файла.",
        "file",
        "Импортировать",
    ),
    PanelAction(
        "import_faculty_reference",
        "Импорт справочника факультетов",
        "Загружает справочник факультетов из файла.",
        "file",
        "Импортировать",
    ),
    PanelAction(
        "import_department_reference",
        "Импорт справочника кафедр",
        "Загружает справочник кафедр из файла.",
        "file",
        "Импортировать",
    ),
    PanelAction(
        "import_schedule",
        "Импорт расписания",
        "Импортирует расписание из файла в выбранном режиме.",
        "file",
        "Импортировать",
        mode_field="mode",
        mode_choices=(
            ("common", "Обычный импорт"),
            ("delete", "Импорт с удалением"),
        ),
    ),
    PanelAction(
        "import_events",
        "Импорт занятий",
        "Импортирует занятия из файла.",
        "file",
        "Импортировать",
    ),
    PanelAction(
        "create_abstract_days",
        "Создать стандартные абстрактные дни",
        "Добавляет стандартный набор абстрактных дней.",
        "button",
        "Создать",
    ),
    PanelAction(
        "create_time_slots",
        "Создать стандартные учебные часы",
        "Добавляет стандартный набор учебных часов.",
        "button",
        "Создать",
    ),
    PanelAction(
        "create_organization",
        "Создать организацию ВолгГТУ",
        "Добавляет базовую организацию, если она еще не существует.",
        "button",
        "Создать",
    ),
    PanelAction(
        "delete_archive_schedules",
        "Удалить архивные расписания",
        "Удаляет все расписания со статусом Архивное.",
        "button",
        "Удалить",
    ),
)

PANEL_ACTIONS_BY_ID = {action.action_id: action for action in PANEL_ACTIONS}


def get_panel_action(action_id: str) -> PanelAction:
    try:
        return PANEL_ACTIONS_BY_ID[action_id]
    except KeyError as exc:
        raise ValueError(f"Unknown panel action: {action_id}") from exc


def run_panel_action(action_id: str, *, upload_path: str = "", mode: str = "") -> str:
    action = get_panel_action(action_id)
    if action.kind == "file" and not upload_path:
        raise ValueError(f"Action {action_id!r} requires an uploaded file.")

    match action_id:
        case "import_subject_reference":
            ReferenceImporter.import_subject_reference(_read_upload(upload_path))
            return "Справочник дисциплин импортирован."
        case "import_teacher_reference":
            ReferenceImporter.import_teacher_reference(_read_upload(upload_path))
            return "Справочник преподавателей импортирован."
        case "import_student_reference":
            ReferenceImporter.import_student_reference(_read_upload(upload_path))
            return "Справочник групп импортирован."
        case "import_place_reference":
            ReferenceImporter.import_place_reference(_read_upload(upload_path))
            return "Справочник аудиторий импортирован."
        case "import_faculty_reference":
            ReferenceImporter.import_faculty_reference(_read_upload(upload_path))
            return "Справочник факультетов импортирован."
        case "import_department_reference":
            ReferenceImporter.import_department_reference(_read_upload(upload_path))
            return "Справочник кафедр импортирован."
        case "import_schedule":
            if mode not in {"common", "delete"}:
                raise ValueError("Unknown schedule import mode.")
            ReferenceImporter.import_schedule(_read_upload(upload_path), mode == "common")
            return "Расписание импортировано."
        case "import_events":
            EventImporter.import_events(_read_upload(upload_path))
            return "Занятия импортированы."
        case "create_abstract_days":
            create_common_abstract_days()
            return "Стандартные абстрактные дни созданы."
        case "create_time_slots":
            create_common_time_slots()
            return "Стандартные учебные часы созданы."
        case "create_organization":
            Organization.objects.get_or_create(name="ВолгГТУ")
            return "Организация ВолгГТУ создана или уже существовала."
        case "delete_archive_schedules":
            deleted_count, _ = Schedule.objects.filter(status=Schedule.Status.ARCHIVE).delete()
            return f"Архивные расписания удалены: {deleted_count}."
        case _:
            raise ValueError(f"Unknown panel action: {action_id}")


def _read_upload(upload_path: str) -> str:
    return Path(upload_path).read_text(encoding="utf-8-sig")
