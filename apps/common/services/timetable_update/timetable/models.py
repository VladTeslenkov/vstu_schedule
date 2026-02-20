from django.db import models
from django.templatetags.static import static


class Tag(models.Model):
    """
    Таблица tag хранит информацию о тегах, которые могут быть связаны с ресурсами.
    """
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200, verbose_name="Название тега")
    category = models.CharField(max_length=200, verbose_name="Название категории тега")

    class Meta:
        db_table = 'tag'
        verbose_name = 'Тег'
        verbose_name_plural = 'Теги'
        app_label = 'timetable'
        constraints = [
            models.UniqueConstraint(fields=['name', 'category'], name='unique_name_category')
        ]

    def __str__(self):
        return f"{self.name} ({self.category})"

class Resource(models.Model):
    """
    Таблица resource хранит основные сведения о ресурсе, такие как имя, путь и метаданные.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._not_save_tags = list()

    id = models.BigAutoField(primary_key=True)
    last_update = models.DateTimeField(auto_now=True, verbose_name="Дата последнего обновления")  # Автоматическое обновление времени
    name = models.CharField(max_length=255, verbose_name="Имя ресурса")  # Имя ресурса
    path = models.TextField(null=True, blank=True, default=None, verbose_name="Путь к ресурсу")  # Путь
    metadata = models.JSONField(null=True, blank=True, default=None, verbose_name="Метаданные")  # JSON-данные
    tags = models.ManyToManyField(
        'Tag',
        related_name='resources',
        blank=True,
        verbose_name="Теги"
    )
    deprecated = models.BooleanField(default=False, verbose_name="Ресурс устарел")
    derived_from = models.ForeignKey(
        'Resource',
        on_delete=models.DO_NOTHING,
        db_column='derived_from_resource_id',
        related_name="derived_resources",
        verbose_name="Исходный ресурс",
        null=True,
        blank=True,
        default=None
    )

    def add_tags(self, *args):
        for tag in args:
            exists = Tag.objects.filter(id=tag.id).exists()
            if exists:
                self.tags.add(tag)
            else:
                self._not_save_tags.append(tag)

    def save(self, *args, **kwargs):
        # Сохраняем элемент в базе данных
        super().save(*args, **kwargs)
        self.save_tags()

    def save_tags(self):
        # Сохраняем в него не сохранённые теги
        for tag in self._not_save_tags:
            saved_tag = Tag.objects.get_or_create(name=tag.name, category=tag.category)[0]
            self.tags.add(saved_tag)
        self._not_save_tags.clear()

    def get_not_saved_tags(self):
        return self._not_save_tags

    class Meta:
        db_table = 'resource'
        verbose_name = 'Ресурс'
        verbose_name_plural = 'Ресурсы'
        app_label = 'timetable'

    def __str__(self):
        return f"{self.name} ({self.path})"


class FileVersion(models.Model):
    """
    Таблица file_version хранит версии файлов, относящиеся к определенному ресурсу.
    """
    id = models.BigAutoField(primary_key=True)
    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        db_column='resource_id',
        related_name="versions",
        verbose_name="Связанный ресурс"
    )
    mimetype = models.CharField(max_length=45, null=True, blank=True, default=None, verbose_name="MIME-тип файла")  # MIME-тип
    url = models.TextField(null=True, blank=True, default=None, verbose_name="URL-адрес файла")  # URL
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания версии")  # Дата создания
    last_changed = models.DateTimeField(null=True, blank=True, default=None, verbose_name="Дата последнего изменения")  # Последнее изменение
    hashsum = models.CharField(max_length=255, verbose_name="Хэш-сумма файла")  # Хэш

    class Meta:
        db_table = 'file_version'
        verbose_name = 'Версия файла'
        verbose_name_plural = 'Версии файлов'
        app_label = 'timetable'

    def __str__(self):
        return f"{self.url} ({self.last_changed} | {self.timestamp}) hash {self.hashsum}"

class Storage(models.Model):
    """
    Таблица storage хранит информацию о местоположении файла и его ссылках на скачивание.
    """
    id = models.BigAutoField(primary_key=True)
    file_version = models.ForeignKey(
        FileVersion,
        on_delete=models.CASCADE,
        db_column='file_version_id',
        related_name="storages",
        verbose_name="Связанная версия файла"
    )
    storage_type = models.CharField(max_length=127, verbose_name="Тип хранилища")  # Тип хранилища
    path = models.TextField(null=True, blank=True, default=None, verbose_name="Путь к файлу")  # Путь
    download_url = models.TextField(null=True, blank=True, default=None, verbose_name="Ссылка для скачивания")  # Скачивание
    resource_url = models.TextField(null=True, blank=True, default=None, verbose_name="Ссылка на ресурс")  # Прямая ссылка
    archive_url = models.TextField(null=True, verbose_name="Ссылка на папку с архивными версиями") # Просмотр архива

    class Meta:
        db_table = 'storage'
        verbose_name = 'Хранилище'
        verbose_name_plural = 'Хранилища'
        app_label = 'timetable'

    def __str__(self):
        return f"{self.path} ({self.storage_type})"

class Task(models.Model):
    id = models.BigAutoField(primary_key=True)
    status = models.CharField(max_length=150, verbose_name="Статус выполнения задачи")
    params = models.JSONField()
    result = models.JSONField(null=True)
    error_message = models.TextField(null=True)

    def __str__(self):
        return f"{self.id}: {self.status}"

class Snapshot(models.Model):
    id = models.BigAutoField(primary_key=True)
    type = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    path = models.TextField(null=True)

    def get_url(self):
        return static(self.path)

class Setting(models.Model):
    key = models.CharField(max_length=255, primary_key=True)  # Уникальное имя настройки
    value = models.TextField()  # Значение настройки
    description = models.TextField(null=True)  # Описание для админки

    def __str__(self):
        return f"{self.key}: {self.value}"
