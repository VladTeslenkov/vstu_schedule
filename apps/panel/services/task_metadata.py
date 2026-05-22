from dataclasses import dataclass

from django.conf import settings

from apps.common.services.celery_task_descriptors import get_task_descriptor


@dataclass(frozen=True)
class TaskMetadata:
    slug: str
    title: str
    description: str


def _language_code() -> str:
    return settings.LANGUAGE_CODE.split("-", maxsplit=1)[0]


def _translated(value: dict[str, str], language: str, fallback: str) -> str:
    return value.get(language) or value.get("en") or fallback


def get_task_metadata(task_name: str, language_code: str | None = None) -> TaskMetadata:
    language = language_code or _language_code()
    descriptor = get_task_descriptor(task_name)
    if descriptor is None:
        return TaskMetadata(slug=task_name.replace(".", "_"), title=task_name, description="")

    return TaskMetadata(
        slug=task_name.replace(".", "_"),
        title=_translated(descriptor.name, language, task_name),
        description=_translated(descriptor.description, language, ""),
    )
