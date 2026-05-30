class PanelTaskConfigurationError(ValueError):
    """Raised when panel task configuration values are invalid."""


class PanelTaskParameterError(ValueError):
    """Raised when panel task parameter values are invalid."""


class CeleryTaskNotRegisteredError(ValueError):
    """Raised when a configured Celery task is missing from the app registry."""
