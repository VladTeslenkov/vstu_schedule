from django.apps import AppConfig


class PanelConfig(AppConfig):
    name = "apps.panel"

    def ready(self) -> None:
        from apps.panel import signals

        _ = signals
