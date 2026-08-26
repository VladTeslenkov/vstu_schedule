from datetime import timedelta

import pytest
from django.utils import timezone

from apps.common.models import FileVersion, Resource, TimetableFileImport
from apps.common.services.timetable_update.prune_versions import prune_resource_versions


@pytest.mark.django_db
def test_prune_resource_versions_keeps_latest_and_removes_stale_files(settings, tmp_path):
    settings.DATA_STORAGE_DIR = tmp_path

    resource = Resource.objects.create(name="Test", path="Test")
    resource_dir = tmp_path / "Test"
    resource_dir.mkdir(parents=True)

    now = timezone.now()

    old_version = FileVersion.objects.create(
        resource=resource,
        url="https://example.com/old.xlsx",
        last_changed=now - timedelta(days=2),
        hashsum="old",
    )
    new_version = FileVersion.objects.create(
        resource=resource,
        url="https://example.com/new.xlsx",
        last_changed=now,
        hashsum="new",
    )
    TimetableFileImport.objects.create(file_version=old_version)

    (resource_dir / "old.xlsx").write_bytes(b"old content")
    (resource_dir / "new.xlsx").write_bytes(b"new content")

    result = prune_resource_versions()

    assert result == {"deleted_versions": 1, "deleted_files": 1}

    remaining_versions = list(FileVersion.objects.filter(resource=resource))
    assert remaining_versions == [new_version]
    assert not TimetableFileImport.objects.filter(file_version=old_version).exists()

    assert not (resource_dir / "old.xlsx").exists()
    assert (resource_dir / "new.xlsx").exists()


@pytest.mark.django_db
def test_prune_resource_versions_noop_for_single_version(settings, tmp_path):
    settings.DATA_STORAGE_DIR = tmp_path

    resource = Resource.objects.create(name="Solo", path="Solo")
    resource_dir = tmp_path / "Solo"
    resource_dir.mkdir(parents=True)

    FileVersion.objects.create(
        resource=resource,
        url="https://example.com/solo.xlsx",
        hashsum="solo",
    )
    (resource_dir / "solo.xlsx").write_bytes(b"content")

    result = prune_resource_versions()

    assert result == {"deleted_versions": 0, "deleted_files": 0}
    assert FileVersion.objects.filter(resource=resource).count() == 1
    assert (resource_dir / "solo.xlsx").exists()


@pytest.mark.django_db
def test_prune_resource_versions_skips_cleanup_when_kept_version_has_no_url(settings, tmp_path):
    settings.DATA_STORAGE_DIR = tmp_path

    resource = Resource.objects.create(name="NoUrl", path="NoUrl")
    resource_dir = tmp_path / "NoUrl"
    resource_dir.mkdir(parents=True)

    FileVersion.objects.create(resource=resource, url=None, hashsum="a")
    (resource_dir / "leftover.xlsx").write_bytes(b"content")

    result = prune_resource_versions()

    assert result == {"deleted_versions": 0, "deleted_files": 0}
    assert (resource_dir / "leftover.xlsx").exists()
