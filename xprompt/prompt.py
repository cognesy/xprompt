from __future__ import annotations

from pathlib import Path
from typing import Any

import frontmatter
import jinja2


class Prompt:
    """Base class for all prompts.

    Subclass and set template_file for external Markdown templates,
    or override body() for programmatic (JSX-style) composition.
    """

    model: str | None = None
    is_block: bool = False
    template_file: str | None = None
    template_dir: Path | None = None

    # Override in subclass to declare composed blocks
    blocks: list[type[Prompt]] = []

    def __init__(self, **kwargs: Any):
        # Store constructor kwargs for parametric blocks
        self._kwargs = kwargs
        self._meta: dict[str, Any] = {}
        self._template: str | None = None

    def body(self, **ctx: Any) -> str | list | None:
        """Return renderable content: str, list of str/Prompt/None, or None.

        Override for programmatic composition. Default loads template_file.
        """
        if self.template_file is not None:
            return self._render_template(**ctx)
        return None

    def render(self, **ctx: Any) -> str:
        """Render this prompt to a string."""
        raw = self.body(**ctx)
        return _flatten(raw)

    def meta(self) -> dict[str, Any]:
        """Return front-matter metadata. Loads template_file if not yet loaded."""
        if not self._meta and self.template_file is not None:
            self._load_template_file()
        return dict(self._meta)

    # -- internals --

    _prompts_root: Path | None = None

    @classmethod
    def set_prompts_root(cls, path: Path | str) -> None:
        """Set the root directory for template file resolution."""
        Prompt._prompts_root = Path(path)

    def _resolve_template_path(self) -> Path:
        if self.template_dir is not None:
            return self.template_dir / self.template_file
        if self._prompts_root is None:
            raise RuntimeError(
                "Prompt.set_prompts_root() must be called before using template_file"
            )
        return self._prompts_root / self.template_file

    def _load_template_file(self) -> None:
        path = self._resolve_template_path()
        post = frontmatter.load(str(path))
        self._meta = dict(post.metadata)
        self._template = post.content

    def _render_template(self, **ctx: Any) -> str:
        if self._template is None:
            self._load_template_file()

        # Build rendered blocks for {{ blocks.ClassName }} substitution
        block_renders: dict[str, str] = {}
        for block_cls in self.blocks:
            instance = block_cls()
            block_renders[block_cls.__name__] = instance.render(**ctx)

        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        tpl = env.from_string(self._template)
        return tpl.render(blocks=block_renders, **ctx)


class NodeSet(Prompt):
    """A prompt component backed by structured data (YAML/inline list of nodes).

    Each node is a dict with required 'id' field + arbitrary metadata.
    Override nodes() to filter/transform, render_node() to format.
    """

    data_file: str | None = None
    sort_key: str | None = None
    items: list[dict[str, Any]] | None = None  # inline alternative to data_file

    def nodes(self, **ctx: Any) -> list[dict[str, Any]]:
        """Load and return nodes. Override to filter/transform."""
        if self.items is not None:
            raw = [dict(n) for n in self.items]
        elif self.data_file is not None:
            raw = self._load_yaml()
        else:
            return []
        if self.sort_key:
            raw.sort(key=lambda n: n.get(self.sort_key, 0))
        return raw

    def render_node(self, index: int, node: dict[str, Any], **ctx: Any) -> str:
        """Render a single node. Override for custom formatting."""
        label = node.get("label", node["id"])
        content = node.get("content", "")
        line = f"{index}. **{label}** -- {content}" if content else f"{index}. **{label}**"
        children = node.get("children", [])
        if children:
            child_lines = [
                f"   - {c.get('content', c.get('label', c['id']))}"
                for c in children
            ]
            line += "\n" + "\n".join(child_lines)
        return line

    def body(self, **ctx: Any) -> list[str]:
        items = self.nodes(**ctx)
        return [self.render_node(i, n, **ctx) for i, n in enumerate(items, 1)]

    def _load_yaml(self) -> list[dict[str, Any]]:
        import yaml

        path = self._resolve_data_path()
        with open(path) as f:
            return yaml.safe_load(f) or []

    def _resolve_data_path(self) -> Path:
        if self._prompts_root is None:
            raise RuntimeError(
                "Prompt.set_prompts_root() must be called before using data_file"
            )
        return self._prompts_root / self.data_file


def _flatten(node: Any) -> str:
    """Recursively flatten a render tree to a string."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, Prompt):
        return node.render()
    if isinstance(node, list):
        parts = [_flatten(n) for n in node]
        return "\n\n".join(p for p in parts if p)
    return str(node)
