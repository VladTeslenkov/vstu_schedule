# ruff: noqa: DJ001
from typing import ClassVar

from django.db import models


class Tag(models.Model):
    """Тег, связанный с ресурсами расписания."""

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200, verbose_name="Название тега")
    category = models.CharField(max_length=200, verbose_name="Название категории тега")

    class Meta:
        db_table = "tag"
        verbose_name = "Тег"
        verbose_name_plural = "Теги"
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["name", "category"], name="unique_name_category")
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.category})"


class Resource(models.Model):
    """
    Ресурс — файл расписания, идентифицируемый путём и метаданными.
    Путь соответствует расположению файла в локальном хранилище (DATA_STORAGE_DIR).
    """

    id = models.BigAutoField(primary_key=True)
    last_update = models.DateTimeField(auto_now=True, verbose_name="Дата последнего обновления")
    name = models.CharField(max_length=255, verbose_name="Имя ресурса")
    # Относительный путь файла внутри DATA_STORAGE_DIR
    path = models.TextField(null=True, blank=True, default=None, verbose_name="Путь к файлу")
    metadata = models.JSONField(null=True, blank=True, default=None, verbose_name="Метаданные")
    tags = models.ManyToManyField(
        Tag,
        related_name="resources",
        blank=True,
        verbose_name="Теги",
    )
    deprecated = models.BooleanField(default=False, verbose_name="Ресурс устарел")

    class Meta:
        db_table = "resource"
        verbose_name = "Ресурс"
        verbose_name_plural = "Ресурсы"
        indexes: ClassVar = [
            models.Index(fields=["deprecated", "-last_update"], name="resource_status_updated_idx"),
            models.Index(fields=["name"], name="resource_name_idx"),
            models.Index(fields=["path", "name"], name="resource_path_name_idx"),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pending_tags: list[Tag] = []

    def __str__(self) -> str:
        return f"{self.name} ({self.path})"

    def save(self, *args, **kwargs) -> None:
        super().save(*args, **kwargs)
        for tag in self._pending_tags:
            saved_tag, _ = Tag.objects.get_or_create(name=tag.name, category=tag.category)
            self.tags.add(saved_tag)
        self._pending_tags.clear()

    def add_tags(self, *tags: "Tag") -> None:
        for tag in tags:
            if Tag.objects.filter(id=tag.id).exists():
                self.tags.add(tag)
            else:
                self._pending_tags.append(tag)


class FileVersion(models.Model):
    """
    Версия файла расписания.
    Хэш используется для определения факта изменения содержимого файла.
    Каждая новая версия — это факт того, что файл изменился на сайте.
    """

    id = models.BigAutoField(primary_key=True)
    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        db_column="resource_id",
        related_name="versions",
        verbose_name="Ресурс",
    )
    mimetype = models.CharField(
        max_length=45, null=True, blank=True, default=None, verbose_name="Расширение файла"
    )
    url = models.TextField(
        null=True, blank=True, default=None, verbose_name="URL источника на сайте"
    )
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Дата обнаружения версии")
    last_changed = models.DateTimeField(
        null=True, blank=True, default=None, verbose_name="Дата изменения по данным сайта"
    )
    hashsum = models.CharField(max_length=255, verbose_name="Контрольная сумма содержимого файла")
    file_name = models.CharField(
        max_length=255, null=True, blank=True, verbose_name="Имя файла на диске"
    )
    archived = models.BooleanField(default=False, verbose_name="Версия заархивирована")

    class Meta:
        db_table = "file_version"
        verbose_name = "Версия файла"
        verbose_name_plural = "Версии файлов"
        indexes: ClassVar = [
            models.Index(fields=["-timestamp", "-id"], name="fileversion_recent_idx"),
            models.Index(
                fields=["resource", "-last_changed", "-timestamp"], name="fv_resource_latest_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.resource.name} | {self.timestamp} | {self.hashsum[:8]}"


class TimetableFileImport(models.Model):
    """Tracks importing a stored timetable file version into schedule tables."""

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает импорта"
        IMPORTED = "imported", "Импортирован"
        FAILED = "failed", "Ошибка импорта"
        SKIPPED = "skipped", "Пропущен"

    id = models.BigAutoField(primary_key=True)
    file_version = models.ForeignKey(
        FileVersion,
        on_delete=models.CASCADE,
        related_name="timetable_imports",
        verbose_name="Версия файла",
    )
    status = models.CharField(
        max_length=32,
        choices=Status,
        default=Status.PENDING,
        verbose_name="Статус",
    )
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата начала")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата завершения")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Метаданные")
    result = models.JSONField(default=dict, blank=True, verbose_name="Результат")
    error = models.TextField(blank=True, default="", verbose_name="Ошибка")

    class Meta:
        db_table = "timetable_file_import"
        verbose_name = "Импорт файла расписания"
        verbose_name_plural = "Импорты файлов расписания"
        indexes: ClassVar = [
            models.Index(fields=["file_version", "status"], name="tfi_version_status_idx")
        ]

    def __str__(self) -> str:
        return f"{self.file_version.pk}: {self.status}"
