from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.api.models import ApiClient


@staff_member_required
def api_clients_panel(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if not name:
            messages.error(request, "Укажите название API-клиента.")
        else:
            created_client, created_secret = ApiClient.create_with_secret(
                name=name,
                created_by=request.user,
            )
            request.session["api_client_secret_flash"] = {
                "client_id": created_client.pk,
                "secret": created_secret,
            }
            messages.success(
                request,
                "API-клиент создан. Секрет показан только сейчас.",
            )
        return redirect("panel_api_clients")

    created_client = None
    created_secret = None
    secret_flash = request.session.pop("api_client_secret_flash", None)
    if secret_flash:
        created_client = ApiClient.objects.filter(pk=secret_flash.get("client_id")).first()
        created_secret = secret_flash.get("secret") if created_client else None

    return render(
        request,
        "panel/api_clients.html",
        {
            "active_nav": "api_clients",
            "clients": ApiClient.objects.select_related("created_by"),
            "created_client": created_client,
            "created_secret": created_secret,
        },
    )


@staff_member_required
def revoke_api_client(request: HttpRequest, client_id: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)

    api_client = get_object_or_404(ApiClient, pk=client_id)
    api_client.revoke()
    messages.success(request, "API-клиент отозван.")
    return redirect("panel_api_clients")


@staff_member_required
def rotate_api_client_secret(request: HttpRequest, client_id: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)

    api_client = get_object_or_404(ApiClient, pk=client_id)
    created_secret = api_client.rotate_secret()
    request.session["api_client_secret_flash"] = {
        "client_id": api_client.pk,
        "secret": created_secret,
    }
    messages.success(
        request,
        "Секрет API-клиента обновлен. Новый секрет показан только сейчас.",
    )
    return redirect("panel_api_clients")
