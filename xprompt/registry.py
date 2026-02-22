from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from xprompt.prompt import Prompt


class PromptRegistry:
    """Central registry for prompt discovery and config-driven variant selection.

    Usage:
        registry = PromptRegistry(overrides={"reviewer.analyze": "AnalyzeCoT"})
        registry.register("reviewer.analyze", Analyze)
        prompt = registry.get("reviewer.analyze")
        text = prompt.render(document=doc, criteria=rules)
    """

    def __init__(
        self,
        prompts_root: str | Path | None = None,
        overrides: dict[str, str] | None = None,
    ):
        self._root = Path(prompts_root) if prompts_root is not None else None
        self._overrides = overrides or {}
        if self._root is not None:
            Prompt.set_prompts_root(self._root)

        # name -> class mapping, built from registered prompts
        self._registry: dict[str, type[Prompt]] = {}
        # name -> {variant_name: class}
        self._variants: dict[str, dict[str, type[Prompt]]] = {}

    def register(self, name: str, cls: type[Prompt]) -> None:
        """Register a prompt class under a dotted name."""
        if name not in self._registry:
            self._registry[name] = cls
        # Always track as variant (class name -> class)
        self._variants.setdefault(name, {})[cls.__name__] = cls

    def get(self, name: str) -> Prompt:
        """Get a prompt instance, applying config overrides if present."""
        if name not in self._registry:
            raise KeyError(f"Unknown prompt: {name!r}")

        override = self._overrides.get(name)
        if override:
            variants = self._variants.get(name, {})
            if override in variants:
                return variants[override]()
            raise KeyError(
                f"Override {override!r} for {name!r} not found. "
                f"Available: {list(variants.keys())}"
            )
        return self._registry[name]()

    def all(self, include_blocks: bool = False) -> Iterator[tuple[str, type[Prompt]]]:
        """Iterate (name, class) pairs. Excludes blocks by default."""
        for name, cls in sorted(self._registry.items()):
            if not include_blocks and cls.is_block:
                continue
            yield name, cls

    def names(self, include_blocks: bool = False) -> list[str]:
        """List registered prompt names."""
        return [name for name, _ in self.all(include_blocks=include_blocks)]


def prompt(name: str):
    """Class decorator to register a prompt under a dotted name.

    Usage:
        @prompt("reviewer.analyze")
        class Analyze(Prompt):
            template_file = "analyze.md"
    """
    def decorator(cls: type[Prompt]) -> type[Prompt]:
        cls._prompt_name = name
        return cls
    return decorator
