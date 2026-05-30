#!/bin/bash
set -e

# Если запускается основной веб-сервер, делаем миграции
if [ "$1" = "gunicorn" ]; then
    echo "Applying migrations..."
    python manage.py migrate --noinput
    echo "Compiling translations..."
    python manage.py compilemessages --locale en --ignore .venv
    echo "Collecting static..."
    python manage.py collectstatic --noinput
fi

exec "$@"
