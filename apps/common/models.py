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
        constraints = [
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pending_tags: list["Tag"] = []

    def add_tags(self, *tags: "Tag") -> None:
        for tag in tags:
            if Tag.objects.filter(id=tag.id).exists():
                self.tags.add(tag)
            else:
                self._pending_tags.append(tag)

    def save(self, *args, **kwargs) -> None:
        super().save(*args, **kwargs)
        for tag in self._pending_tags:
            saved_tag, _ = Tag.objects.get_or_create(name=tag.name, category=tag.category)
            self.tags.add(saved_tag)
        self._pending_tags.clear()

    class Meta:
        db_table = "resource"
        verbose_name = "Ресурс"
        verbose_name_plural = "Ресурсы"

    def __str__(self) -> str:
        return f"{self.name} ({self.path})"


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
    mimetype = models.CharField(max_length=45, null=True, blank=True, default=None, verbose_name="Расширение файла")
    url = models.TextField(null=True, blank=True, default=None, verbose_name="URL источника на сайте")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Дата обнаружения версии")
    last_changed = models.DateTimeField(null=True, blank=True, default=None, verbose_name="Дата изменения по данным сайта")
    hashsum = models.CharField(max_length=255, verbose_name="SHA-256 хэш содержимого файла")

    class Meta:
        db_table = "file_version"
        verbose_name = "Версия файла"
        verbose_name_plural = "Версии файлов"

    def __str__(self) -> str:
        return f"{self.resource.name} | {self.timestamp} | {self.hashsum[:8]}"


class Setting(models.Model):
    """Настройки проекта в формате ключ-значение. Управляются через панель."""

    key = models.CharField(max_length=255, primary_key=True, verbose_name="Ключ")
    value = models.TextField(verbose_name="Значение")
    description = models.TextField(null=True, blank=True, verbose_name="Описание")

    class Meta:
        db_table = "setting"
        verbose_name = "Настройка"
        verbose_name_plural = "Настройки"

    def __str__(self) -> str:
        return f"{self.key}: {self.value}"
