from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from celery import shared_task

from vstu_schedule.tasks.concurrency import celery_task_concurrency_lock

_TaskFunc = TypeVar("_TaskFunc", bound=Callable[..., Any])


def project_task(*decorator_args: Any, **task_options: Any) -> Callable[[_TaskFunc], Any]: # type: ignore
    """
    Register a project Celery task and apply the task descriptor policy.

    Use this decorator instead of `celery.shared_task` for project tasks declared
    in app-level `tasks` packages. It delegates registration to `shared_task`
    and wraps execution with the descriptor-driven `concurrency` policy from
    `tasks/tasks.toml`, so the task's parallel-execution behavior stays next to
    its name, description, timeouts, and recommended schedule.
    """
    if task_options.get("bind") is False:
        raise ValueError("Project Celery tasks must be bound tasks.")
    task_options.setdefault("bind", True)

    def decorate(func: _TaskFunc) -> Any:
        @wraps(func)
        def wrapped(self: Any, *args: Any, **kwargs: Any) -> Any:
            with celery_task_concurrency_lock(self.name, self.request.id) as acquired:
                if not acquired:
                    return {
                        "status": "skipped",
                        "reason": "concurrency_policy",
                        "message": "Task skipped by concurrency policy.",
                    }
                return func(self, *args, **kwargs)

        return shared_task(**task_options)(wrapped)

    if decorator_args and callable(decorator_args[0]) and len(decorator_args) == 1:
        return decorate(cast(_TaskFunc, decorator_args[0]))
    if decorator_args:
        raise TypeError("project_task does not support positional Celery options.")
    return decorate
