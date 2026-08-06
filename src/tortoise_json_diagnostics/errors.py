from dataclasses import dataclass

from jsonschema import Validator, ValidationError

from .types import Location


@dataclass(frozen=True, slots=True)
class JsonDiagnosticError(Exception):
    message: str
    path: tuple[str | int, ...]
    location: Location | None

    def __post_init__(self) -> None:
        super().__init__(self.message)


@dataclass(frozen=True, slots=True)
class SingleValidationError(JsonDiagnosticError):
    validator: Validator
    validation_error: ValidationError


type TJsonDiagnosticError = JsonDiagnosticError | ExceptionGroup[TJsonDiagnosticError]
