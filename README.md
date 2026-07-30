# Расписания ВолгГТУ

Интерактивная визуализация расписаний для ВолгГТУ с целью заменить скачивание Excel-файлов

**Запуск с Nginx на хосте:** настройте окружение в `.env` (см. `.env.example`), включая `WEB_PORT`, `STATIC_HOST_PATH` и `MEDIA_HOST_PATH`, затем выполните:

```bash
docker compose -f docker-compose.yml -f docker-compose.host.yml up -d --build
```

Системный Nginx должен проксировать запросы приложения на `127.0.0.1:${WEB_PORT}` и раздавать `/static/` и `/media/` из каталогов `STATIC_HOST_PATH` и `MEDIA_HOST_PATH`.

**Если Nginx нужен в контейнере:** `docker compose --profile full up -d --build` (подтянет Nginx автоматически). Для остановки используйте `docker compose --profile full down`.

**Локальная разработка**: установите пакетный менеджер `uv` и выполните `uv sync`, после чего будет создано виртуальное окружение проекта в папке `.venv`, перед запуском настройте окружение в файле `.env.local` (см. содержимое `.env.example`). Убедитесь, что имеете запущенную базу данных PostgreSQL

В случае, если необходимо поднять отдельные контейнеры
```bash
docker run -d --name redis -p 6379:6379 redis # redis
uv run celery -A vstu_schedule worker -l info --pool=solo  # worker
uv run celery -A vstu_schedule beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler # celery beat
```

Возможно, для работы сборки переводов на Windows требуется установить `GNU gettext`, например через `winget install --id=GnuWin32.GetText -e`


**[Инструкции для новых разработчиков](/docs/developers.md)**

**Перед отправкой коммита:**
Отформатируйте код:

```bash
uv run ruff format .
```

Проверьте, исходный код на проблемы:

```bash
uv run ruff check .  # Проверка стиля кода
uv run ruff format --check . # Проверка, что файлы отформатированы
uv run pyright # Проверка, что типы не нарушены
```
