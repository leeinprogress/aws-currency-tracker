class UserNotFoundError(Exception):
    pass


class AlertNotFoundError(Exception):
    pass


class DuplicateAlertError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class RateNotFoundError(Exception):
    pass


class ScoringUnavailableError(Exception):
    pass


class InsufficientDataError(Exception):
    def __init__(self, message: str, min_required: int, actual: int) -> None:
        super().__init__(message)
        self.min_required = min_required
        self.actual = actual
