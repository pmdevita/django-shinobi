import inspect
from typing import Any, Callable, Dict, Optional, Type

from django.conf import settings
from django.http import HttpRequest, HttpResponseForbidden
from django.middleware.csrf import CsrfViewMiddleware

__all__ = [
    "check_csrf",
    "is_debug_server",
    "normalize_path",
    "contribute_operation_callback",
]


def replace_path_param_notation(path: str) -> str:
    return path.replace("{", "<").replace("}", ">")


def normalize_path(path: str) -> str:
    while "//" in path:
        path = path.replace("//", "/")
    return path


def _no_view() -> None:
    pass  # pragma: no cover


def check_csrf(
    request: HttpRequest, callback: Callable = _no_view
) -> Optional[HttpResponseForbidden]:
    mware = CsrfViewMiddleware(lambda x: HttpResponseForbidden())  # pragma: no cover
    request.csrf_processing_done = False  # type: ignore
    mware.process_request(request)
    return mware.process_view(request, callback, (), {})


def is_debug_server() -> bool:
    """Check if running under the Django Debug Server"""
    return settings.DEBUG and any(
        s.filename.endswith("runserver.py") and s.function == "run"
        for s in inspect.stack(0)[1:]
    )


def is_async_callable(f: Callable[..., Any]) -> bool:
    return inspect.iscoroutinefunction(f) or inspect.iscoroutinefunction(
        getattr(f, "__call__", None)
    )


def is_optional_type(t: Type[Any]) -> bool:
    try:
        return type(None) in t.__args__
    except AttributeError:
        return False


def contribute_operation_callback(
    func: Callable[..., Any], callback: Callable[..., Any]
) -> None:
    if not hasattr(func, "_ninja_contribute_to_operation"):
        func._ninja_contribute_to_operation = []  # type: ignore
    func._ninja_contribute_to_operation.append(callback)  # type: ignore


def contribute_operation_args(
    func: Callable[..., Any], arg_name: str, arg_type: Type, arg_source: Any
) -> None:
    if not hasattr(func, "_ninja_contribute_args"):
        func._ninja_contribute_args = []  # type: ignore
    func._ninja_contribute_args.append((arg_name, arg_type, arg_source))  # type: ignore


def get_annotations(namespace: Dict[str, Any]) -> Any:
    """
    Inspecting annotations was changed in Python 3.14
    :param namespace:
    :return:
    """
    # Python 3.13 and earlier
    if "__annotations__" in namespace:
        return namespace.get("__annotations__", {})

    # Python 3.14 and newer
    try:
        import annotationlib
    except ImportError:
        return {}

    func = annotationlib.get_annotate_from_class_namespace(namespace)
    if func:
        return annotationlib.call_annotate_function(
            func, format=annotationlib.Format.FORWARDREF
        )
    # Pydantic should error for any class missing type annotations
    return {}  # pragma: no cover
