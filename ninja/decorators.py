import asyncio
from functools import partial
from typing import (
    Any,
    Callable,
    Coroutine,
    Generic,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from typing_extensions import ParamSpec, Self

from ninja.operation import Operation
from ninja.types import TCallable
from ninja.utils import contribute_operation_callback

# Since @api.method decorator is applied to function
# that is not always returns a HttpResponse object
# there is no way to apply some standard decorators form
# django stdlib or public plugins
#
# @decorate_view allows to apply any view decorator to Ninja api operation
#
# @api.get("/some")
# @decorate_view(cache_page(60 * 15)) # <-------
# def some(request):
#     ...
#


def decorate_view(*decorators: Callable[..., Any]) -> Callable[[TCallable], TCallable]:
    def outer_wrapper(op_func: TCallable) -> TCallable:
        if hasattr(op_func, "_ninja_operation"):
            # Means user used decorate_view on top of @api.method
            _apply_decorators(decorators, op_func._ninja_operation)  # type: ignore
        else:
            # Means user used decorate_view after(bottom) of @api.method
            contribute_operation_callback(
                op_func, partial(_apply_decorators, decorators)
            )

        return op_func

    return outer_wrapper


def _apply_decorators(
    decorators: Tuple[Callable[..., Any]], operation: Operation
) -> None:
    for deco in decorators:
        operation.run = deco(operation.run)  # type: ignore


ArgT = ParamSpec("ArgT")
ReturnT = TypeVar("ReturnT")

Instance = TypeVar("Instance")


class asyncable(Generic[ReturnT]):
    """Decorator to make a function callable from both sync and async contexts

    Example:
    @asyncable
    def my_function(request):
        return HttpResponse("Hello, world!")

    @my_function.asynchronous
    async def my_function_async(request):
        return HttpResponse("Hello, world!")


    resp = my_function() # Sync call
    resp = await my_function() # Async call

    More details: https://itsjohannawren.medium.com/single-call-sync-and-async-in-python-2acadd07c9d6
    """

    def __init__(self, method: Callable[..., ReturnT]) -> None:
        self.__sync = method
        self.__async: Optional[Callable[..., ReturnT]] = None

    def asynchronous(self, method: Callable[..., ReturnT]) -> "asyncable":
        self.__async = method
        return self

    def __is_awaited(self) -> bool:
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False

    def __get__(
        self, instance: Optional[Instance], ownerclass: Type[Instance]
    ) -> Union[
        Self, Callable[..., ReturnT], Callable[..., Coroutine[Any, Any, ReturnT]]
    ]:
        if instance is None:
            return self
        if self.__is_awaited():
            if self.__async is None:
                raise RuntimeError(
                    "Attempting to call asyncable with await, but no asynchronous call has been defined"
                )

            async def async_closure(*args: ArgT.args, **kwargs: ArgT.kwargs) -> ReturnT:
                assert self.__async is not None
                bound_method: Callable[ArgT, Coroutine[Any, Any, ReturnT]] = (
                    self.__async.__get__(instance, ownerclass)
                )
                return await bound_method(*args, **kwargs)

            return async_closure

        def sync_closure(*args: ArgT.args, **kwargs: ArgT.kwargs) -> ReturnT:
            bound_method: Callable[ArgT, ReturnT] = self.__sync.__get__(
                instance, ownerclass
            )
            return bound_method(*args, **kwargs)

        return sync_closure

    def __call__(self, *args: ArgT.args, **kwargs: ArgT.kwargs) -> ReturnT:
        if self.__is_awaited():
            if self.__async is None:
                raise RuntimeError(
                    "Attempting to call asyncable with await, but no asynchronous call has been defined"
                )
            return self.__async(*args, **kwargs)
        return self.__sync(*args, **kwargs)
