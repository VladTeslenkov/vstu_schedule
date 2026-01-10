import os
from typing import Any


def get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default)).lower()
    return value in ("1", "true", "yes", "on")


def get_list(name: str, default: list | None = None, sep: str = ',') -> list:
    value = os.getenv(name, "")
    if not value:
        return default or []
    return [item.strip() for item in value.split(",")]


def get(name: str, default: Any = "") -> str:
    return os.getenv(name, default)
