class TooManyEventsFoundError(Exception):
    def __init__(self, limit: int) -> None:
        self.limit = limit
        super().__init__(f"Found more than {limit} events.")


class InvalidDateFilterError(Exception):
    """Raised when schedule date filter values cannot be parsed."""
