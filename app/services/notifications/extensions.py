"""Loading helpers for locally installed messenger adapter extensions."""

from __future__ import annotations

from importlib import import_module
from typing import Callable, TYPE_CHECKING

from app.services.notifications.base import BaseMessengerAdapter

if TYPE_CHECKING:
    from app.services.notifications.manager import NotificationManager


def load_adapter(spec: str, manager: "NotificationManager") -> BaseMessengerAdapter:
    """Load an adapter from a ``python.module:factory`` specification."""
    module_name, separator, factory_name = spec.partition(":")
    if not separator or not module_name or not factory_name:
        raise ValueError(
            f"Invalid messenger adapter '{spec}'. Expected 'python.module:factory'."
        )

    factory: Callable = getattr(import_module(module_name), factory_name)
    if not callable(factory):
        raise TypeError(f"Messenger factory '{spec}' is not callable.")
    adapter = factory(manager)
    if not isinstance(adapter, BaseMessengerAdapter):
        raise TypeError(f"Messenger factory '{spec}' must return a BaseMessengerAdapter.")
    return adapter
