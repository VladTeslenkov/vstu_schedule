from django.apps import AppConfig


class PanelConfig(AppConfig):
    name = "apps.panel"

    def ready(self) -> None:
        from django.core.checks import Tags, register

        from apps.panel import signals
        from vstu_schedule.tasks.descriptors import task_descriptor_system_check

        _ = signals
        register(Tags.compatibility)(task_descriptor_system_check)
