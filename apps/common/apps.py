from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.common"

    def ready(self):
        from apps.common import signals

        signals.register_common_model_signals()
        # TODO: не дописано?
