from collections.abc import Sequence
from dataclasses import dataclass
import difflib
from typing import cast

from jsonschema import Validator, ValidationError
from jsonschema._utils import find_additional_properties

from .base import IValidationHandler
from ..formatters import TextSpan, ErrorMessageFormatter, get_global_message_formatter
from ..errors import SingleValidationError
from ..types import SourceDocument, Location, SpanTarget
from ..typing import Json


def find_suggestion(invalid_key: str, allowed_keys: set[str], cutoff: float = 0.6) -> str | None:
    suggestions: list[str] = difflib.get_close_matches(invalid_key, allowed_keys, n=1, cutoff=cutoff)
    return suggestions[0] if suggestions else None


@dataclass(frozen=True, slots=True)
class AdditionalPropertyError(SingleValidationError):
    extra: str


class AdditionalPropertiesHandler(IValidationHandler):
    def handle(self, validator: Validator, validation_errors: Sequence[ValidationError], /, source_document: SourceDocument) -> tuple[Sequence[SingleValidationError], Sequence[ValidationError]]:
        errors: list[SingleValidationError] = []

        unhandle_errors: list[ValidationError] = []

        for validation_error in validation_errors:
            if validation_error.validator != "additionalProperties":
                unhandle_errors.append(validation_error)
                continue

            instance = cast(dict[str, Json], validation_error.instance)
            schema = cast(dict[str, list[str]], validation_error.schema)

            extras: set[str] = set(find_additional_properties(instance, schema))
            for extra in extras:
                json_path: tuple[str | int, ...] = (*validation_error.absolute_path, extra)
                span: TextSpan | None = source_document.get_span(json_path, target=SpanTarget.KEY)

                if "patternProperties" in schema:
                    patterns = ", ".join(repr(each) for each in sorted(schema["patternProperties"]))
                    title = f"{extra!r} does not match any of the regexes: {patterns}"
                else:
                    title = f"Additional properties are not allowed ({extra!r} was unexpected)"

                properties = cast(dict[str, Json], schema.get("properties", {}))
                allowed_keys: set[str] = set(properties.keys())
                suggestion: str | None = find_suggestion(extra, allowed_keys)
                if suggestion is not None:
                    title = f"{title}. Did you mean: {suggestion!r}?"

                formatter: ErrorMessageFormatter = get_global_message_formatter()
                message: str = formatter.format(title, source_document, span)

                location: Location | None = span.start if span else None

                error = AdditionalPropertyError(message, tuple(validation_error.absolute_path), location, validator, validation_error, extra)

                errors.append(error)

        return errors, unhandle_errors
