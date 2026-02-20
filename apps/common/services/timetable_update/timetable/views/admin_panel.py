import asyncio
import json
import threading
import os
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from timetable_project.settings import GOOGLE_AUTH_FILE
from timetable.apps import AVAILABLE_KEYS, GOOGLE_DRIVE_STORAGE_MAME, LOCAL_STORAGE_NAME
from timetable.models import Task, Snapshot, Setting
from timetable.task.make_task import make_task
from timetable.cron_utils import configure_update_task

storage_types = {
    "Google Drive": GOOGLE_DRIVE_STORAGE_MAME,
    "Yandex Drive": "",
    "Локальное хранилище": LOCAL_STORAGE_NAME,
}
snapshot_types = [
    "Вся система",
    "База данных",
    "Google Drive",
    "Yandex Drive",
    "Локальное хранилище",
]
clear_types = [
    "Вся система",
    "Все хранилища",
    "Google Drive",
    "Yandex Drive",
    "Локальное хранилище",
]


def admin_login(request):
    """
    Обработчик авторизации.
    """
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            login(request, user)
            return redirect("admin_panel")
        else:
            return render(
                request,
                "admin_login.html",
                {"error": "Неверные учетные данные или нет доступа"},
            )
    return render(request, "admin_login.html")


@login_required
def admin_panel(request):
    """
    Обработчик панели администратора.
    """
    if not request.user.is_staff:
        return redirect("admin_login")

    # Проверяем наличие файла google_drive_auth.json
    auth_file_exists = os.path.exists(GOOGLE_AUTH_FILE)

    params = {
        "storage_types": storage_types,
        "snapshot_types": snapshot_types,
        "clear_types": clear_types,
        "time_update_value": (
            Setting.objects.get(key="time_update").value
            if Setting.objects.filter(key="time_update").exists()
            else "180"
        ),
        "auth_file_exists": auth_file_exists,  # Передаем информацию о наличии файла
    }
    return render(request, "admin_panel.html", params)


def put_google_auth_file(request):
    """Обновить файл авторизации Google."""
    if request.method == "POST":
        try:
            uploaded_file = request.FILES.get("authFile")
            if not uploaded_file:
                return JsonResponse(
                    {"status": "error", "error_message": "Файл не загружен"}, status=400
                )
            with open(GOOGLE_AUTH_FILE, "wb") as f:
                for chunk in uploaded_file.chunks():
                    f.write(chunk)
            return JsonResponse({"status": "success"}, status=200)
        except Exception as e:
            return JsonResponse(
                {"status": "error", "error_message": str(e)}, status=400
            )
    return HttpResponse(status=400)


@login_required
def set_system_params(request):
    """Обработчик для установки системных параметров."""
    if not request.user.is_staff:
        return JsonResponse(
            {"status": "error", "error_message": "Доступ запрещён"}, status=403
        )

    if request.method == "POST":
        try:
            # Получаем данные из POST-запроса
            scan_frequency = request.POST.get("scanFrequency")
            root_url = request.POST.get("rootUrl")
            storage_type = request.POST.get("storageType")

            # Сохраняем частоту сканирования
            if scan_frequency:
                try:
                    scan_frequency = int(scan_frequency)
                    setting, created = Setting.objects.get_or_create(key="time_update")
                    setting.value = str(scan_frequency)
                    setting.description = "Частота обновления расписания в минутах"
                    setting.save()

                    # Переконфигурируем задачу APScheduler
                    configure_update_task()
                except ValueError:
                    return JsonResponse(
                        {
                            "status": "error",
                            "error_message": "Некорректное значение частоты сканирования",
                        },
                        status=400,
                    )

            # Сохраняем корневую ссылку
            if root_url:
                setting, created = Setting.objects.get_or_create(key="analyze_url")
                setting.value = root_url
                setting.description = "Корневая ссылка для анализа расписания"
                setting.save()

            # Сохраняем тип хранилища
            if storage_type:
                setting, created = Setting.objects.get_or_create(key="download_storage")
                setting.value = storage_type
                setting.description = "Тип хранилища для скачивания файлов"
                setting.save()

            return JsonResponse({"status": "success"}, status=200)
        except Exception as e:
            return JsonResponse(
                {"status": "error", "error_message": str(e)}, status=400
            )

    return JsonResponse(
        {"status": "error", "error_message": "Метод не поддерживается"}, status=400
    )


def snapshot(request):
    """Обработчик создания снимков системы."""
    if request.method == "POST":
        action = request.POST.get("action")
        snapshot = request.POST.get("snapshot")
        params = {
            "action": action,
            "snapshot": snapshot,
        }
        snapshot_task = Task.objects.create(status="running", params=params)
        threading.Thread(target=asyncio.run, args=(make_task(snapshot_task),)).start()
        return JsonResponse(
            {"status": snapshot_task.status, "id": snapshot_task.id}, status=202
        )
    elif request.method == "GET":
        keys = request.GET.keys()
        if "process_id" in keys:
            process_id = request.GET.get("process_id")
            task = Task.objects.get(id=int(process_id))
            if task is not None:
                return JsonResponse(
                    {
                        "status": task.status,
                        "result": task.result,
                        "error_message": task.error_message,
                    },
                    status=200,
                )
        elif "snapshot_type" in keys:
            snapshot_type = request.GET.get("snapshot_type")
            snapshot = (
                Snapshot.objects.filter(type=snapshot_type)
                .order_by("-timestamp")
                .first()
            )
            if snapshot is not None:
                return JsonResponse({"url": snapshot.get_url()}, status=200)
            else:
                return JsonResponse({"url": ""}, status=200)
    return HttpResponse(status=400)


def manage_storage(request):
    """Обработчик управления хранилищами."""
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "dell":
            component = request.POST.get("component")
            params = {
                "action": action,
                "component": component,
            }
            snapshot_task = Task.objects.create(status="running", params=params)
            threading.Thread(
                target=asyncio.run, args=(make_task(snapshot_task),)
            ).start()
            return JsonResponse(
                {"status": snapshot_task.status, "id": snapshot_task.id}, status=202
            )
    elif request.method == "GET":
        keys = request.GET.keys()
        if "process_id" in keys:
            process_id = request.GET.get("process_id")
            task = Task.objects.get(id=int(process_id))
            if task is not None:
                return JsonResponse(
                    {
                        "status": task.status,
                        "result": task.result,
                        "error_message": task.error_message,
                    },
                    status=200,
                )
    return HttpResponse(status=400)


def update_timetable(request):
    """Обработчик запуска обновления расписания."""
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update_timetable":
            params = {
                "action": action,
            }
            update_task = Task.objects.create(status="running", params=params)
            threading.Thread(target=asyncio.run, args=(make_task(update_task),)).start()
            return JsonResponse(
                {"status": update_task.status, "id": update_task.id}, status=202
            )
    elif request.method == "GET":
        keys = request.GET.keys()
        if "process_id" in keys:
            process_id = request.GET.get("process_id")
            try:
                task = Task.objects.get(id=int(process_id))
                return JsonResponse(
                    {
                        "status": task.status,
                        "result": task.result,
                        "error_message": task.error_message,
                    },
                    status=200,
                )
            except Task.DoesNotExist:
                return JsonResponse(
                    {"status": "error", "error_message": "Задача не найдена"},
                    status=404,
                )
    return HttpResponse(status=400)
