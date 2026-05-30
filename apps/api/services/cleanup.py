from apps.api.models import ApiClient


def delete_revoked_api_clients() -> int:
    deleted_count, _ = ApiClient.objects.filter(revoked_at__isnull=False).delete()
    return deleted_count
