# Agent Instructions

This file complements `docs/developers.md` and provides concise working rules for LLM agents and other automated coding assistants.

## Project Context

- This is a Django 6.x project for an interactive university timetable.
- Minimum Python version: 3.13.
- Dependencies are managed with `uv`; do not add `requirements.txt`.
- Main applications live under `apps/`:
  - `apps/common` contains shared models, selectors, tests, and reusable business logic.
  - `apps/client` handles the user-facing timetable visualization.
  - `apps/panel` handles the admin panel and background tasks.
- Django project settings live in `vstu_schedule/`.
- Documentation and long algorithm descriptions should live in `docs/`.

## Architecture Rules

- Treat `common` as a shared library-like app. Do not add web views to it.
- Put complex business logic in `services/`, not in models or views.
- Django ORM may be used in business logic when it keeps the code simpler.
- Use selector functions in `selectors.py` for reusable database reads.
- Avoid fat models: keep only behavior that naturally belongs to the model itself.
- Views should contain only HTTP and web concerns; move shared or complex logic into `services/`.
- Migrations should cover schema and data changes; do not require separate SQL scripts.
- When changing Django models, create or update migrations with Django management commands, not by hand:

```powershell
uv run python manage.py makemigrations
```

- After model changes, run a migration check before the final response when possible:

```powershell
uv run python manage.py makemigrations --check --dry-run
```

- Do not manually write normal schema migrations. Manual migration files are acceptable only for Django migration graph maintenance such as merge migrations, or for carefully reviewed custom data migrations when Django cannot generate the needed operation.
- If `makemigrations` cannot run because the local database or environment is unavailable, mention that in the final response and do not silently skip the migration step.

## Code Style

- Write code for Python 3.13 and use modern type annotations such as `list[str]` and `str | None`.
- Follow PEP8, SOLID, DRY, and KISS.
- Add types for new and changed code.
- Add short comments or docstrings only for non-trivial logic.
- Use the standard `logging` module for business-logic logging when needed.
- Do not add secrets, real tokens, private data, or unnecessary generated files.
- Prefer unrealistic sample data for public tests instead of real university schedules.
- New third-party dependencies must be justified and added with `uv`.

## Checks

Before the final response after code changes, run the relevant checks when possible.

Install or sync dependencies:

```powershell
uv sync
```

Ruff linter:

```powershell
uv run ruff check .
```

Ruff formatting check:

```powershell
uv run ruff format --check .
```

Pyright type checker:

```powershell
uv run pyright
```

Pytest test suite:

```powershell
uv run pytest
```

For narrow changes, targeted checks are acceptable, for example:

```powershell
uv run pytest apps/common/tests/test_utility_filters.py
uv run ruff check apps/common/services/timetable/utilities
```

If a check cannot run because of missing external services, environment variables, permissions, or network restrictions, mention that clearly in the final response.

## Local Run

- The main development run mode is Docker Compose.
- Start the project with:

```powershell
docker compose up -d --build
```

- Running locally without Docker is possible, but it requires an available PostgreSQL database and, when needed, Celery/Redis.
- To partially disable Celery in local mode, set `DISABLE_CELERY=1` in `.env.local`.
- Celery tasks declared in an app `tasks` package must be exported from its `__init__.py` and described in `tasks/tasks.toml`.
- New dependencies will not appear inside already running containers without rebuilding the images.

## Working With Changes

- Do not rewrite unrelated parts of the project.
- Do not delete or revert changes made by others unless explicitly asked.
- Cover complex new business logic with `pytest` tests.
- If new logic is too large to explain in code comments, add Markdown documentation under `docs/` and reference it from the code.
- In the final response, list which checks were run and how they finished.
