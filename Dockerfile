# --- Этап 1: Сборка (Builder) ---
FROM python:3.13-slim AS builder

# Копируем uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# КРИТИЧЕСКИ ВАЖНО: заставляем uv Копировать библиотеки, а не делать ссылки
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# Системные зависимости (git нужен для вашей зависимости из GitHub)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы зависимостей
COPY pyproject.toml uv.lock ./

# Устанавливаем зависимости
# --no-install-project: не ставим сам код проекта как пакет, только библиотеки
RUN uv sync --frozen --no-dev --no-install-project

# --- Этап 2: Финальный образ (Runtime) ---
FROM python:3.13-slim

# Настройки Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Добавляем виртуальное окружение в PATH и объявляем его основным
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Устанавливаем только библиотеку для работы с Postgres
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Копируем готовое виртуальное окружение из билдера (теперь там реальные файлы, а не ссылки)
COPY --from=builder /opt/venv /opt/venv

# Копируем код проекта
COPY . .

# Права на запуск
RUN chmod +x /app/entrypoint.sh && \
    mkdir -p /app/static /app/media

ENTRYPOINT ["/app/entrypoint.sh"]