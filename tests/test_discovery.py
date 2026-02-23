from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from xprompt import Prompt, PromptRegistry, prompt
from xprompt.addons.discovery import discover_prompts, register_discovered


@pytest.fixture
def package_root(tmp_path: Path):
    root = tmp_path / "sampleapp"
    root.mkdir()
    (root / "__init__.py").write_text("")

    (root / "classifier").mkdir()
    (root / "classifier" / "__init__.py").write_text("")
    (root / "classifier" / "prompts.py").write_text(
        "from xprompt import Prompt, prompt\n"
        "@prompt('classifier.classify_content')\n"
        "class ClassifyContent(Prompt):\n"
        "    def body(self, **ctx):\n"
        "        return 'content'\n"
    )

    (root / "observer").mkdir()
    (root / "observer" / "__init__.py").write_text("")
    (root / "observer" / "prompts.py").write_text(
        "from xprompt import Prompt\n"
        "class ExtractSignals(Prompt):\n"
        "    def body(self, **ctx):\n"
        "        return 'signals'\n"
    )

    sys.path.insert(0, str(tmp_path))
    importlib.invalidate_caches()
    yield "sampleapp"

    for key in list(sys.modules):
        if key == "sampleapp" or key.startswith("sampleapp."):
            del sys.modules[key]
    if str(tmp_path) in sys.path:
        sys.path.remove(str(tmp_path))


def test_discover_prompts_mixed_explicit_and_convention(package_root: str):
    discovered = discover_prompts(package_root)

    assert "classifier.classify_content" in discovered
    assert "observer.extract_signals" in discovered


def test_register_discovered_into_registry(package_root: str):
    reg = PromptRegistry()
    registered = register_discovered(reg, package_root)

    assert "classifier.classify_content" in registered
    assert "observer.extract_signals" in registered

    prompt_instance = reg.get("observer.extract_signals")
    assert isinstance(prompt_instance, Prompt)
    assert prompt_instance.render() == "signals"


def test_discover_duplicate_names_raises(tmp_path: Path):
    root = tmp_path / "dupeapp"
    root.mkdir()
    (root / "__init__.py").write_text("")

    (root / "a").mkdir()
    (root / "a" / "__init__.py").write_text("")
    (root / "a" / "prompts.py").write_text(
        "from xprompt import Prompt\n"
        "class SameName(Prompt):\n"
        "    prompt_name = 'shared.name'\n"
    )

    (root / "b").mkdir()
    (root / "b" / "__init__.py").write_text("")
    (root / "b" / "prompts.py").write_text(
        "from xprompt import Prompt\n"
        "class Another(Prompt):\n"
        "    prompt_name = 'shared.name'\n"
    )

    sys.path.insert(0, str(tmp_path))
    importlib.invalidate_caches()
    try:
        with pytest.raises(ValueError, match="Duplicate prompt name"):
            discover_prompts("dupeapp")
    finally:
        for key in list(sys.modules):
            if key == "dupeapp" or key.startswith("dupeapp."):
                del sys.modules[key]
        if str(tmp_path) in sys.path:
            sys.path.remove(str(tmp_path))


def test_discover_skips_block_prompts_by_default(tmp_path: Path):
    root = tmp_path / "blockapp"
    root.mkdir()
    (root / "__init__.py").write_text("")
    (root / "diag").mkdir()
    (root / "diag" / "__init__.py").write_text("")
    (root / "diag" / "prompts.py").write_text(
        "from xprompt import Prompt\n"
        "class SharedBlock(Prompt):\n"
        "    is_block = True\n"
        "class Diagnose(Prompt):\n"
        "    pass\n"
    )

    sys.path.insert(0, str(tmp_path))
    importlib.invalidate_caches()
    try:
        discovered = discover_prompts("blockapp")
        assert "diag.shared_block" not in discovered
        assert "diag.diagnose" in discovered

        with_blocks = discover_prompts("blockapp", include_blocks=True)
        assert "diag.shared_block" in with_blocks
    finally:
        for key in list(sys.modules):
            if key == "blockapp" or key.startswith("blockapp."):
                del sys.modules[key]
        if str(tmp_path) in sys.path:
            sys.path.remove(str(tmp_path))
