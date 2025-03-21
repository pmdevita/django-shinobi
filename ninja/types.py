from typing import Any, Callable, Dict, TypeVar, Annotated, TypeAliasType, Type

__all__ = ["DictStrAny", "TCallable"]

from django.db.models import Manager, QuerySet, FileField
from django.db.models.fields.files import ImageFieldFile, FieldFile
from pydantic import BeforeValidator, GetJsonSchemaHandler, GetCoreSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema

DictStrAny = Dict[str, Any]

TCallable = TypeVar("TCallable", bound=Callable[..., Any])


# unfortunately this doesn't work yet, see
# https://github.com/python/mypy/issues/3924
# Decorator = Callable[[TCallable], TCallable]

# Todo: Actually figure out how to type this correctly for Pydantic
FileFieldType = str

