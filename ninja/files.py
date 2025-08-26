from typing import Callable, Dict, Union

from django.core.files.uploadedfile import UploadedFile as DjangoUploadedFile
from django.db.models.fields.files import FieldFile, FileField
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema
from typing_extensions import Annotated, Any

__all__ = ["UploadedFile"]

from pydantic_core.core_schema import (
    BeforeValidatorFunctionSchema,
    ChainSchema,
    ValidationInfo,
)


class UploadedFile(DjangoUploadedFile):
    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: Any, handler: Callable[..., Any]
    ) -> Dict:
        # calling handler(core_schema) here raises an exception
        json_schema: Dict[str, str] = {}
        json_schema.update(type="string", format="binary")
        return json_schema

    @classmethod
    def _validate(cls, v: Any, _: Any) -> Any:
        if not isinstance(v, DjangoUploadedFile):
            raise ValueError(f"Expected UploadFile, received: {type(v)}")
        return v

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: Any, handler: Callable[..., Any]
    ) -> Any:
        return core_schema.with_info_plain_validator_function(cls._validate)


def validate_file_field(value: Any, info: ValidationInfo) -> Any:
    if isinstance(value, FieldFile):
        if not value:
            return None
        return value.url
    return value


class _FileFieldType:
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        from ninja.signature.details import is_optional

        # Deprecate: Pydantic 2.6-2.7 do not support model_type_stack
        if hasattr(_handler._generate_schema, "model_type_stack"):  # type: ignore[attr-defined]
            # Introspect the field using this type to determine if it's supposed to be optional
            # TODO: Make a test that creates a stack > 1
            if (
                len(_handler._generate_schema.model_type_stack._stack) != 1  # type: ignore[attr-defined]
            ):
                raise Exception(
                    "Unexpected issue creating a schema with a FileField. Please open an issue on Django Shinobi."
                )  # pragma: no cover

            file_field_schema: Union[BeforeValidatorFunctionSchema, ChainSchema] = (
                core_schema.chain_schema([
                    core_schema.with_info_before_validator_function(
                        validate_file_field, core_schema.str_schema()
                    ),
                    core_schema.str_schema(),
                ])
            )

            field = _handler._generate_schema.model_type_stack._stack[  # type: ignore[attr-defined]
                0
            ].model_fields[_handler.field_name]

            optional = is_optional(field.annotation)
        else:
            # Older versions of Pydantic do not return this info
            # Set optional to True just in case (this was the old behavior anyway, we're just being more honest now)
            optional = True

        if optional:
            field_type = core_schema.union_schema([
                core_schema.str_schema(),
                core_schema.none_schema(),
            ])
            file_field_schema = core_schema.with_info_before_validator_function(
                validate_file_field, field_type
            )

        return core_schema.json_or_python_schema(
            json_schema=file_field_schema, python_schema=file_field_schema
        )


FileFieldType = Annotated[FileField, _FileFieldType]
