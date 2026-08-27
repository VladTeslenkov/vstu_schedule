import logging
from pathlib import Path

from django.conf import settings

from apps.common.models import FileVersion, Resource
from apps.common.services.timetable_update.version_core.file_data import FileData

logger = logging.getLogger(__name__)


def prune_resource_versions() -> dict[str, int]:
    """
    Для каждого ресурса оставляет только последнюю версию файла (FileVersion),
    остальные версии удаляет из БД. Также удаляет из файлового хранилища файлы,
    не соответствующие оставленной версии.
    """
    storage_dir = settings.DATA_STORAGE_DIR
    deleted_versions = 0
    deleted_files = 0

    for resource in Resource.objects.all():
        versions = list(
            FileVersion.objects.filter(resource=resource).order_by("-last_changed", "-timestamp")
        )
        if not versions:
            continue

        kept_version, *stale_versions = versions

        if stale_versions:
            FileVersion.objects.filter(id__in=[v.id for v in stale_versions]).delete()
            deleted_versions += len(stale_versions)
            logger.info(
                "Pruned %s stale version(s) for resource %s", len(stale_versions), resource.id
            )

        deleted_files += _prune_resource_files(storage_dir, resource, kept_version)

    logger.info(
        "Resource version pruning completed: %s versions removed, %s files removed",
        deleted_versions,
        deleted_files,
    )
    return {"deleted_versions": deleted_versions, "deleted_files": deleted_files}


def _prune_resource_files(storage_dir: Path, resource: Resource, kept_version: FileVersion) -> int:
    """Удаляет из директории ресурса все файлы, кроме относящегося к оставленной версии."""
    resource_dir = storage_dir / (resource.path or resource.name)
    if not resource_dir.is_dir():
        return 0

    if not kept_version.url:
        logger.warning("Resource %s kept version has no URL, skipping storage cleanup", resource.id)
        return 0

    keep_name = FileData.get_file_name_from_path(kept_version.url, dell_mimetype=False)

    deleted = 0
    for item in resource_dir.iterdir():
        if not item.is_file() or item.name == keep_name:
            continue
        item.unlink()
        deleted += 1
        logger.debug("Removed stale file: %s", item)

    return deleted
