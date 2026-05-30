import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone


class ApiClient(models.Model):
    name = models.CharField(max_length=255)
    client_id = models.CharField(max_length=64, unique=True, db_index=True)
    client_secret_hash = models.CharField(max_length=255)
    allowed_scopes = models.CharField(max_length=255, blank=True, default="read")
    is_active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_api_clients",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    secret_rotated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.name} ({self.client_id})"

    @classmethod
    def create_with_secret(cls, *, name: str, created_by=None) -> tuple["ApiClient", str]:
        secret = generate_client_secret()
        client = cls(
            name=name,
            client_id=generate_client_id(),
            client_secret_hash=make_password(secret),
            created_by=created_by,
        )
        client.save()
        return client, secret

    def verify_secret(self, secret: str) -> bool:
        return check_password(secret, self.client_secret_hash)

    def rotate_secret(self) -> str:
        secret = generate_client_secret()
        self.client_secret_hash = make_password(secret)
        self.secret_rotated_at = timezone.now()
        self.save(update_fields=("client_secret_hash", "secret_rotated_at", "updated_at"))
        return secret

    def revoke(self) -> None:
        self.is_active = False
        self.revoked_at = timezone.now()
        self.save(update_fields=("is_active", "revoked_at", "updated_at"))

    def mark_used(self) -> None:
        self.last_used_at = timezone.now()
        self.save(update_fields=("last_used_at", "updated_at"))

    @property
    def scope_list(self) -> list[str]:
        return [scope.strip() for scope in self.allowed_scopes.split(",") if scope.strip()]


def generate_client_id() -> str:
    return f"vstu_{secrets.token_urlsafe(24)}"


def generate_client_secret() -> str:
    return secrets.token_urlsafe(48)
