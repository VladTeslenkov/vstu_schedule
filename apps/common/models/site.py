# ruff: noqa: DJ001
from typing import ClassVar

from django.db import models
from django.utils import timezone, translation


class Setting(models.Model):
    """Настройки проекта в формате ключ-значение."""

    key = models.CharField(max_length=255, primary_key=True, verbose_name="Ключ")
    value = models.TextField(verbose_name="Значение")
    description = models.TextField(null=True, blank=True, verbose_name="Описание")

    class Meta:
        db_table = "setting"
        verbose_name = "Настройка"
        verbose_name_plural = "Настройки"

    def __str__(self) -> str:
        return f"{self.key}: {self.value}"


class Alert(models.Model):
    class Category(models.TextChoices):
        DANGER = "danger", "Критическое"
        WARNING = "warning", "Предупреждение"
        SUCCESS = "success", "Успех"
        NOTICE = "notice", "Уведомление"

    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255, verbose_name="Заголовок")
    body = models.TextField(verbose_name="Текст")
    title_en = models.CharField(
        max_length=255, blank=True, default="", verbose_name="Заголовок (английский)"
    )
    body_en = models.TextField(blank=True, default="", verbose_name="Текст (английский)")
    category = models.CharField(
        max_length=16,
        choices=Category,
        default=Category.NOTICE,
        verbose_name="Категория",
    )
    is_enabled = models.BooleanField(default=True, verbose_name="Включено")
    is_admin = models.BooleanField(
        default=False, verbose_name="Показывать только в панели администратора"
    )
    is_dismissible = models.BooleanField(default=True, verbose_name="Пользователь может закрыть")
    starts_at = models.DateTimeField(
        null=True, blank=True, default=None, verbose_name="Дата начала показа"
    )
    expires_at = models.DateTimeField(
        null=True, blank=True, default=None, verbose_name="Дата окончания показа"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        db_table = "alert"
        verbose_name = "Оповещение"
        verbose_name_plural = "Оповещения"
        indexes: ClassVar = [
            models.Index(
                fields=["is_enabled", "is_admin", "starts_at", "expires_at"],
                name="alert_active_idx",
            ),
        ]
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.title

    @property
    def display_title(self) -> str:
        if translation.get_language() == "en" and self.title_en:
            return self.title_en
        return self.title

    @property
    def display_body(self) -> str:
        if translation.get_language() == "en" and self.body_en:
            return self.body_en
        return self.body

    @property
    def icon_name(self) -> str:
        return {
            self.Category.DANGER: "alert-triangle",
            self.Category.WARNING: "alert-triangle",
            self.Category.SUCCESS: "check",
            self.Category.NOTICE: "info",
        }[self.category]

    @property
    def is_currently_active(self) -> bool:
        now = timezone.now()
        starts_ok = self.starts_at is None or self.starts_at <= now
        expires_ok = self.expires_at is None or self.expires_at > now
        return self.is_enabled and starts_ok and expires_ok
