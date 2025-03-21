from typing import Any, Callable, Dict, TypeVar

__all__ = ["DictStrAny", "TCallable"]


DictStrAny = Dict[str, Any]

TCallable = TypeVar("TCallable", bound=Callable[..., Any])


# unfortunately this doesn't work yet, see
# https://github.com/python/mypy/issues/3924
# Decorator = Callable[[TCallable], TCallable]

# Todo: Actually figure out how to type this correctly for Pydantic
FileFieldType = str
