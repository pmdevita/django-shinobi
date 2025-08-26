"""
Since "Model" word would be very confusing when used in django context, this
module basically makes an alias for it named "Schema" and adds extra whistles to
be able to work with django querysets and managers.

The schema is a bit smarter than a standard pydantic Model because it can handle
dotted attributes and resolver methods. For example::


    class UserSchema(User):
        name: str
        initials: str
        boss: str = Field(None, alias="boss.first_name")

        @staticmethod
        def resolve_name(obj):
            return f"{obj.first_name} {obj.last_name}"

"""

import warnings
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union, no_type_check

import pydantic
from django.db.models import Manager, QuerySet
from django.db.models.fields.files import FieldFile
from django.template import Variable, VariableDoesNotExist
from pydantic import (
    BaseModel,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
    validator,
)
from pydantic._internal._model_construction import ModelMetaclass
from pydantic.fields import FieldInfo
from pydantic.functional_validators import ModelWrapValidatorHandler
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from typing_extensions import dataclass_transform

from ninja.conf import settings
from ninja.signature.details import is_classvar_type, is_collection_type
from ninja.signature.utils import get_args_names, has_kwargs
from ninja.types import DictStrAny

pydantic_version = list(map(int, pydantic.VERSION.split(".")[:2]))
assert pydantic_version >= [2, 0], "Pydantic 2.0+ required"

__all__ = ["BaseModel", "Field", "validator", "DjangoGetter", "Schema"]

S = TypeVar("S", bound="Schema")


class DjangoGetter:
    __slots__ = ("_obj", "_schema_cls", "_context", "__dict__")

    def __init__(self, obj: Any, schema_cls: Type[S], context: Any = None):
        self._obj = obj
        self._schema_cls = schema_cls
        self._context = context

    def __getattr__(self, key: str) -> Any:
        # if key.startswith("__pydantic"):
        #     return getattr(self._obj, key)

        resolver = self._schema_cls._ninja_resolvers.get(key)
        if resolver:
            value = resolver(getter=self)
        else:
            if isinstance(self._obj, dict):
                if key not in self._obj:
                    raise AttributeError(key)
                value = self._obj[key]
            else:
                try:
                    value = getattr(self._obj, key)
                except AttributeError:
                    try:
                        # value = attrgetter(key)(self._obj)
                        value = Variable(key).resolve(self._obj)
                        # TODO: Variable(key) __init__ is actually slower than
                        #       Variable.resolve - so it better be cached
                    except VariableDoesNotExist as e:
                        raise AttributeError(key) from e
        return self._convert_result(value)

    # def get(self, key: Any, default: Any = None) -> Any:
    #     try:
    #         return self[key]
    #     except KeyError:
    #         return default

    def _convert_result(self, result: Any) -> Any:
        if isinstance(result, Manager):
            return list(result.all())

        elif isinstance(result, getattr(QuerySet, "__origin__", QuerySet)):
            return list(result)

        if callable(result):
            return result()

        elif isinstance(result, FieldFile):
            if not result:
                return None
            return result.url

        return result

    def __repr__(self) -> str:
        return f"<DjangoGetter: {repr(self._obj)}>"


class ObjectPatcher:
    __slots__ = ("_obj", "_dict")

    def __init__(self, obj: Any):
        self._obj = obj
        self._dict: Dict[str, Any] = {}

    def __getattr__(self, key: str) -> Any:
        if key in self._dict:
            value = self._dict[key]
        else:
            if isinstance(self._obj, dict):
                if key not in self._obj:
                    raise AttributeError(key)
                value = self._obj[key]
            else:
                value = getattr(self._obj, key)
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        self._dict[key] = value

    def __repr__(self) -> str:
        return f"<ObjectPatcher: {repr(self._obj)} + {repr(self._dict)}>"


class Resolver:
    __slots__ = ("_func", "_static", "_takes_context")
    _static: bool
    _func: Any
    _takes_context: bool

    def __init__(self, func: Union[Callable, staticmethod]):
        if isinstance(func, staticmethod):
            self._static = True
            self._func = func.__func__
        else:
            self._static = False
            self._func = func

        arg_names = get_args_names(self._func)
        self._takes_context = has_kwargs(self._func) or "context" in arg_names

    def run(self, value: Any, info: Any) -> Any:
        kwargs = {}
        if self._takes_context:
            kwargs["context"] = info

        if self._static:
            return self._func(value, **kwargs)
        raise NotImplementedError(
            "Non static resolves are not supported yet"
        )  # pragma: no cover

    def __call__(self, getter: DjangoGetter) -> Any:
        kwargs = {}
        if self._takes_context:
            kwargs["context"] = getter._context

        if self._static:
            return self._func(getter._obj, **kwargs)
        raise NotImplementedError(
            "Non static resolves are not supported yet"
        )  # pragma: no cover
        # return self._func(self._fake_instance(getter), getter._obj)

    # def _fake_instance(self, getter: DjangoGetter) -> "Schema":
    #     """
    #     Generate a partial schema instance that can be used as the ``self``
    #     attribute of resolver functions.
    #     """

    #     class PartialSchema(Schema):
    #         def __getattr__(self, key: str) -> Any:
    #             value = getattr(getter, key)
    #             field = getter._schema_cls.model_fields[key]
    #             value = field.validate(value, values={}, loc=key, cls=None)[0]
    #             return value

    #     return PartialSchema()


@dataclass_transform(kw_only_default=True, field_specifiers=(Field,))
class ResolverMetaclass(ModelMetaclass):
    _ninja_resolvers: Dict[str, Resolver]
    _aliases: Dict[str, str]

    @no_type_check
    def __new__(cls, name, bases, namespace, **kwargs):
        resolvers = {}
        aliases = {}
        compatibility: Optional[bool] = namespace.get("_compatibility", None)
        if compatibility is None:
            compatibility = settings.COMPATIBILITY

        for base in reversed(bases):
            base_resolvers = getattr(base, "_ninja_resolvers", None)
            if base_resolvers:
                resolvers.update(base_resolvers)
        for attr, resolve_func in namespace.items():
            if not attr.startswith("resolve_"):
                continue
            if (
                not callable(resolve_func)
                # A staticmethod isn't directly callable in Python <=3.9.
                and not isinstance(resolve_func, staticmethod)
            ):
                continue  # pragma: no cover
            resolvers[attr[8:]] = Resolver(resolve_func)

        # Check for string alias paths and register them
        for field_name, field in namespace.items():
            if not isinstance(field, FieldInfo):
                continue
            alias = field.validation_alias or field.alias
            if isinstance(alias, str) and "." in alias:
                aliases[field_name] = alias

        # When the base Schema class is being created, do not attach
        # resolver validators, otherwise subclasses won't be able to override them
        if bases != (BaseModel,):
            # Always attach DjangoGetter in compatibility mode
            # in case the user attaches any model/field validators
            if compatibility:
                namespace["__ninja_resolvers_validator"] = model_validator(mode="wrap")(
                    _run_root_validator
                )
            else:
                # We only need to attach the full resolver validator if it's used
                if resolvers or aliases:
                    namespace["__ninja_resolvers_validator"] = model_validator(
                        mode="before"
                    )(_validate_resolvers)

                # Rewrite any annotations looking for collections to include the ManagerValidator
                for annotation_name, annotation in namespace.get(
                    "__annotations__", {}
                ).items():
                    if annotation_name.startswith("_") or is_classvar_type(annotation):
                        continue
                    # Attach a validator to evaluate QuerySets for collection type fields
                    if is_collection_type(annotation):
                        namespace[f"__ninja_manager_validator_{annotation_name}"] = (
                            field_validator(
                                annotation_name, mode="before"
                            )(_manager_to_queryset)
                        )

        result = super().__new__(cls, name, bases, namespace, **kwargs)
        result._ninja_resolvers = resolvers
        result._aliases = aliases
        return result


def _manager_to_queryset(value: Union[Manager, Any]) -> Union[QuerySet, Any]:
    if isinstance(value, Manager):
        return value.all()
    return value


def _validate_resolvers(cls: Type["Schema"], value: Any, info: ValidationInfo) -> Any:
    wrapped = ObjectPatcher(value)

    # Resolve path aliases
    for path in cls._aliases.values():
        # Don't apply alias if this is a key of an attribute on this object
        if hasattr(value, path):
            continue

        if hasattr(value, "__getitem__"):
            try:
                value.__getitem__(path)
                continue
            except KeyError:
                pass

        try:
            wrapped[path] = Variable(path).resolve(value)
        except VariableDoesNotExist:
            pass

    # Evaluate resolvers
    for key, func in cls._ninja_resolvers.items():
        wrapped[key] = func.run(value, info.context)

    return wrapped


def _run_root_validator(
    cls: Any,
    values: Any,
    handler: ModelWrapValidatorHandler[S],
    info: ValidationInfo,
) -> Any:
    # If Pydantic intends to validate against the __dict__ of the immediate Schema
    # object, then we need to call `handler` directly on `values` before the conversion
    # to DjangoGetter, since any checks or modifications on DjangoGetter's __dict__
    # will not persist to the original object.
    forbids_extra = cls.model_config.get("extra") == "forbid"
    should_validate_assignment = cls.model_config.get("validate_assignment", False)
    if forbids_extra or should_validate_assignment:
        handler(values)

    values = DjangoGetter(values, cls, info.context)
    return handler(values)


class NinjaGenerateJsonSchema(GenerateJsonSchema):
    def default_schema(self, schema: Any) -> JsonSchemaValue:
        # Pydantic default actually renders null's and default_factory's
        # which really breaks swagger and django model callable defaults
        # so here we completely override behavior
        json_schema = self.generate_inner(schema["schema"])

        default = None
        if "default" in schema and schema["default"] is not None:
            default = self.encode_default(schema["default"])

        if "$ref" in json_schema:
            # Since reference schemas do not support child keys, we wrap the reference schema in a single-case allOf:
            result = {"allOf": [json_schema]}
        else:
            result = json_schema

        if default is not None:
            result["default"] = default

        return result


class Schema(BaseModel, metaclass=ResolverMetaclass):
    _compatibility: Optional[bool] = None

    class Config:
        from_attributes = True  # aka orm_mode

    @classmethod
    def from_orm(cls: Type[S], obj: Any, **kw: Any) -> S:
        return cls.model_validate(obj, **kw)

    def dict(self, *a: Any, **kw: Any) -> DictStrAny:
        "Backward compatibility with pydantic 1.x"
        return self.model_dump(*a, **kw)

    @classmethod
    def json_schema(cls) -> DictStrAny:
        return cls.model_json_schema(schema_generator=NinjaGenerateJsonSchema)

    @classmethod
    def schema(cls) -> DictStrAny:  # type: ignore
        warnings.warn(
            ".schema() is deprecated, use .json_schema() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return cls.json_schema()
