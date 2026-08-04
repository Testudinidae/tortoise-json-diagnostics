from collections.abc import Sequence

from jsonschema import Validator, ValidationError


class JsonValidationError(Exception):
    def __init__(self, message: str, validator: Validator, validation_errors: Sequence[ValidationError]) -> None:
        super().__init__(message)

        self.message = message
        self.validator = validator
        self.validation_errors = validation_errors


type TJsonValidationError = JsonValidationError | ExceptionGroup[TJsonValidationError]
