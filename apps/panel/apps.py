from django.apps import AppConfig


class PanelConfig(AppConfig):
    name = "apps.panel"

    def ready(self) -> None:
        from django.core.checks import Tags, register

        from apps.common.services.celery_task_descriptors import task_descriptor_system_check
        from apps.panel import signals

        _ = signals
        register(Tags.compatibility)(task_descriptor_system_check)
