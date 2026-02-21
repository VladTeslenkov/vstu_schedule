import logging
import os

from celery.result import AsyncResult
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render

from apps.common.models import Setting

logger = logging.getLogger(__name__)

CLEAR_TYPES = ["Вся система", "Хранилище", "База данных"]


# ======================== АВТОРИЗАЦИЯ ========================


def admin_login(request: HttpRequest) -> HttpResponse:
    """Страница авторизации в панель управления."""
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            login(request, user)
            return redirect("admin_panel")
        return render(request, "admin_login.html", {"error": "Неверные учётные данные или нет доступа"})
    return render(request, "admin_login.html")


# ======================== ПАНЕЛЬ ========================


@login_required
def admin_panel(request: HttpRequest) -> HttpResponse:
    """Главная страница панели управления."""
    if not request.user.is_staff:
        return redirect("admin_login")

    time_update = "180"
    if Setting.objects.filter(key="time_update").exists():
        time_update = Setting.objects.get(key="time_update").value

    context = {
        "clear_types": CLEAR_TYPES,
        "time_update_value": time_update,
    }
    return render(request, "admin_panel.html", context)


# ======================== НАСТРОЙКИ ========================


@login_required
def set_system_params(request: HttpRequest) -> JsonResponse:
    """Сохраняет системные параметры: интервал обновления и URL анализа."""
    if not request.user.is_staff:
        return JsonResponse({"status": "error", "error_message": "Доступ запрещён"}, status=403)
    if request.method != "POST":
        return JsonResponse({"status": "error", "error_message": "Метод не поддерживается"}, status=405)

    try:
        scan_frequency = request.POST.get("scanFrequency")
        root_url = request.POST.get("rootUrl")

        if scan_frequency:
            minutes = int(scan_frequency)
            setting, _ = Setting.objects.get_or_create(key="time_update")
            setting.value = str(minutes)
            setting.description = "Частота обновления расписания в минутах"
            setting.save()

            from apps.panel.tasks import configure_periodic_update
            configure_periodic_update(minutes)

        if root_url:
            setting, _ = Setting.objects.get_or_create(key="analyze_url")
            setting.value = root_url
            setting.description = "Корневая ссылка для анализа расписания"
            setting.save()

        return JsonResponse({"status": "success"})
    except ValueError:
        return JsonResponse({"status": "error", "error_message": "Некорректное значение частоты"}, status=400)
    except Exception as e:
        logger.error(f"set_system_params error: {e}", exc_info=True)
        return JsonResponse({"status": "error", "error_message": str(e)}, status=500)


# ======================== ВСПОМОГАТЕЛЬНОЕ ========================


def _task_status_response(task_id: str) -> JsonResponse:
    """Возвращает текущий статус Celery-задачи по её ID."""
    result = AsyncResult(task_id)
    status_map = {
        "SUCCESS": "success",
        "FAILURE": "error",
        "PENDING": "running",
        "STARTED": "running",
        "RETRY": "running",
    }
    status = status_map.get(result.status, "running")
    error_message = str(result.result) if result.failed() else None
    return JsonResponse({"status": status, "error_message": error_message})


# ======================== ЗАДАЧИ ========================


@login_required
def run_update_timetable(request: HttpRequest) -> JsonResponse | HttpResponse:
    """
    POST — запускает задачу обновления расписания.
    GET ?task_id=... — возвращает статус запущенной задачи.
    """
    if not request.user.is_staff:
        return JsonResponse({"status": "error", "error_message": "Доступ запрещён"}, status=403)

    if request.method == "POST":
        from apps.panel.tasks import update_timetable as update_task
        from celery import Celery  # noqa
        result = update_task.delay()  # type: ignore[union-attr]
        logger.info(f"update_timetable launched: task_id={result.id}")
        return JsonResponse({"status": "running", "id": result.id}, status=202)

    if request.method == "GET" and "task_id" in request.GET:
        return _task_status_response(request.GET["task_id"])

    return HttpResponse(status=400)


@login_required
def manage_storage(request: HttpRequest) -> JsonResponse | HttpResponse:
    """
    POST — запускает задачу очистки хранилища.
    GET ?task_id=... — возвращает статус задачи.
    """
    if not request.user.is_staff:
        return JsonResponse({"status": "error", "error_message": "Доступ запрещён"}, status=403)

    if request.method == "POST" and request.POST.get("action") == "dell":
        component = request.POST.get("component", "")
        from apps.panel.tasks import clear_storage_task
        result = clear_storage_task.delay(component)  # type: ignore[union-attr]
        logger.info(f"clear_storage launched: component={component!r}, task_id={result.id}")
        return JsonResponse({"status": "running", "id": result.id}, status=202)

    if request.method == "GET" and "task_id" in request.GET:
        return _task_status_response(request.GET["task_id"])

    return HttpResponse(status=400)
