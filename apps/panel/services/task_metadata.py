import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from django.conf import settings

_TRANSLATIONS_PATH = Path(__file__).resolve().parent.parent / "translations" / "celery_tasks.toml"


@dataclass(frozen=True)
class TaskMetadata:
    slug: str
    title: str
    description: str


def task_slug(task_name: str) -> str:
    return task_name.replace(".", "_")


@lru_cache(maxsize=1)
def _metadata_config() -> dict[str, Any]:
    if not _TRANSLATIONS_PATH.exists():
        return {}
    with _TRANSLATIONS_PATH.open("rb") as file:
        return tomllib.load(file)


def _language_code() -> str:
    return settings.LANGUAGE_CODE.split("-", maxsplit=1)[0]


def get_task_metadata(task_name: str, language_code: str | None = None) -> TaskMetadata:
    language = language_code or _language_code()
    slug = task_slug(task_name)
    config = _metadata_config()
    task_config = config.get(language, {}).get(slug)
    if task_config is None and language != "en":
        task_config = config.get("en", {}).get(slug)

    if task_config is None:
        title = task_name
        description = ""
    else:
        title = str(task_config.get("title") or task_name)
        description = str(task_config.get("description") or "")

    return TaskMetadata(slug=slug, title=title, description=description)
