import inspect
from collections.abc import Callable
from types import SimpleNamespace
from typing import Annotated, Any, cast, get_args, get_origin

from fastapi import Request
from fastapi.params import Depends


class MockRequest:
    """Mock class that mimics the state of a FastAPI Request object"""

    def __init__(self, state_attrs: dict[str, Any] | None = None):
        # Convert dict to object for attribute access (e.g., request.state.db)
        self.state = SimpleNamespace(**(state_attrs or {}))
        self.scope = {"type": "http"}  # Basic scope info (expand if needed)


def resolve_dependency[T](
    target: Callable[..., T] | type[T],
    state: dict[str, Any] | None = None,
    overrides: dict[Callable, Any] | None = None,
) -> T:
    """
    Test helper that resolves FastAPI dependency trees and creates objects.

    Args:
        target: Class or function to instantiate/call (Service, Repository, etc.)
        state: Key-value pairs to inject into request.state (e.g., {"db": mock_session})
        overrides: Replace specific dependency functions with mock objects {get_db: mock_session}
    """
    if overrides is None:
        overrides = {}

    # 1. Check overrides (highest priority)
    if target in overrides:
        return overrides[target]

    # 2. Inject MockRequest when Request object is needed
    # (Type hint is Request or FastAPI Request class itself)
    if target is Request:
        return cast(T, MockRequest(state))

    # 3. Check if callable (Function or Class)
    if inspect.isclass(target):
        sig_func = target.__init__
    elif callable(target):
        sig_func = target
    else:
        return target  # Return if already an instance

    sig = inspect.signature(sig_func)
    kwargs = {}

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue

        # --- Detect Request object type hint ---
        # Example: def get_db(request: Request): ...
        if param.annotation is Request:
            kwargs[param_name] = MockRequest(state)
            continue

        dependency_target = None

        # --- Case A: Annotated[Type, Depends(...)] ---
        if get_origin(param.annotation) is Annotated:
            for arg in get_args(param.annotation)[1:]:
                if isinstance(arg, Depends):
                    dependency_target = arg.dependency or get_args(param.annotation)[0]
                    break

        # --- Case B: Depends(...) (Default value) ---
        if dependency_target is None and isinstance(param.default, Depends):
            dependency_target = param.default.dependency or param.annotation

        # --- Recursive resolution ---
        if dependency_target:
            # Pass state and overrides recursively
            kwargs[param_name] = resolve_dependency(dependency_target, state, overrides)

        # For normal parameters without explicit dependency, use default if available, otherwise ignore (or error)
        elif param.default is not inspect.Parameter.empty:
            kwargs[param_name] = param.default

    # 4. Instantiate and return object
    if inspect.isclass(target):
        return cast(T, target(**kwargs))
    else:
        return cast(Callable[..., T], target)(**kwargs)
