from __future__ import annotations

import importlib
import inspect
import pkgutil
import re
from collections.abc import Callable, Iterable
from typing import Literal

from xprompt.prompt import Prompt
from xprompt.registry import PromptRegistry

NameResolver = Callable[[type[Prompt]], str | None]


def discover_prompts(
    packages: str | Iterable[str],
    *,
    include_blocks: bool = False,
    allow_convention: bool = True,
    name_resolver: NameResolver | None = None,
    on_error: Literal["raise", "skip"] = "raise",
) -> dict[str, type[Prompt]]:
    """Discover Prompt subclasses from one or more package roots.

    Name resolution order:
    1) ``@prompt`` decorator (``_prompt_name``)
    2) ``prompt_name`` class attribute
    3) Convention (optional): ``<service>.<snake_case(ClassName)>`` when class
       is in a module path containing ``.prompts`` (service = segment before
       ``prompts``).
    """
    package_names = [packages] if isinstance(packages, str) else list(packages)
    resolve_name = name_resolver or (
        lambda cls: _default_name(cls, allow_convention=allow_convention)
    )

    discovered: dict[str, type[Prompt]] = {}
    for module_name in _iter_module_names(package_names):
        module = _import_module(module_name, on_error=on_error)
        if module is None:
            continue

        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls is Prompt or not issubclass(cls, Prompt):
                continue
            if cls.__module__ != module.__name__:
                continue
            if cls.is_block and not include_blocks:
                continue

            name = resolve_name(cls)
            if not name:
                continue

            if name in discovered and discovered[name] is not cls:
                raise ValueError(
                    f"Duplicate prompt name {name!r}: "
                    f"{discovered[name].__module__}.{discovered[name].__name__} and "
                    f"{cls.__module__}.{cls.__name__}"
                )
            discovered[name] = cls

    return discovered


def register_discovered(
    registry: PromptRegistry,
    packages: str | Iterable[str],
    *,
    include_blocks: bool = False,
    allow_convention: bool = True,
    name_resolver: NameResolver | None = None,
    on_error: Literal["raise", "skip"] = "raise",
) -> dict[str, type[Prompt]]:
    """Discover prompts and register them into the given PromptRegistry."""
    discovered = discover_prompts(
        packages,
        include_blocks=include_blocks,
        allow_convention=allow_convention,
        name_resolver=name_resolver,
        on_error=on_error,
    )
    for name, cls in discovered.items():
        registry.register(name, cls)
    return discovered


def _iter_module_names(package_names: list[str]) -> set[str]:
    names: set[str] = set()
    for package_name in package_names:
        module = importlib.import_module(package_name)
        names.add(module.__name__)

        module_path = getattr(module, "__path__", None)
        if not module_path:
            continue

        prefix = f"{module.__name__}."
        for mod_info in pkgutil.walk_packages(module_path, prefix):
            names.add(mod_info.name)

    return names


def _import_module(module_name: str, on_error: Literal["raise", "skip"]):
    try:
        return importlib.import_module(module_name)
    except Exception:
        if on_error == "skip":
            return None
        raise


def _default_name(cls: type[Prompt], *, allow_convention: bool) -> str | None:
    if hasattr(cls, "_prompt_name"):
        value = getattr(cls, "_prompt_name")
        if isinstance(value, str) and value:
            return value

    if hasattr(cls, "prompt_name"):
        value = getattr(cls, "prompt_name")
        if isinstance(value, str) and value:
            return value

    if not allow_convention:
        return None

    parts = cls.__module__.split(".")
    if "prompts" in parts:
        idx = parts.index("prompts")
        if idx > 0:
            service = parts[idx - 1]
            return f"{service}.{_to_snake(cls.__name__)}"

    return _to_snake(cls.__name__)


def _to_snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
