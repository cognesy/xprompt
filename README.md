# xprompt

Prompts-as-code micro-library. ~200 lines. Two dependencies (`jinja2`, `python-frontmatter`).

Each prompt is a Python class. Template text lives in Markdown files or inline.
Composition, versioning, and metadata are native Python -- not config, not YAML,
not a custom DSL.


## Install

```bash
pip install xprompt
```


## Why

Prompts embedded as inline strings create four problems:

1. **Invisible.** Buried in f-strings inside service methods.
2. **Unversioned.** Changing a prompt means changing Python source. No side-by-side comparison.
3. **Untestable for A/B.** Running an experiment requires a code change, a run, another code change to revert.
4. **Coupled.** The person tuning prompts edits the same files as the person writing pipeline logic.


## What xprompt gives you

- **Prompts are classes.** Identity, metadata, composition, and behavior are Python. Template text stays in Markdown (or inline for short blocks).
- **Composition is a list.** `body()` returns `[Block(), "string", None]`. `_flatten()` recursively renders the tree. 15 lines. No Jinja2 needed for assembly.
- **Variants are subclasses.** `class AnalyzeCoT(Analyze)` overrides `template_file`, inherits everything else.
- **Config-driven switching.** One line in your config swaps a variant. No code change.
- **Strict rendering.** Jinja2 `StrictUndefined` -- missing variables raise immediately.


## Quick start

### 1. Define a prompt

```python
from xprompt import Prompt

class AnalyzeDocument(Prompt):
    model = "sonnet"
    template_file = "analyze.md"
```

Template file (`prompts/analyze.md`):

```markdown
---
description: Analyze document against evaluation criteria
---
Analyze {{ content }} against {{ criteria_text }}.

For each criterion where you find evidence, extract an observation.
```

### 2. Use it

```python
prompt = AnalyzeDocument()
text = prompt.render(content=doc_text, criteria_text=formatted_criteria)
model = prompt.model       # "sonnet"
meta = prompt.meta()       # {"description": "Analyze document against..."}
```

### 3. Colocate with your module

Set `template_dir` to resolve templates relative to the prompt class, not a global root:

```python
from pathlib import Path
from xprompt import Prompt

_DIR = Path(__file__).resolve().parent

class AnalyzeDocument(Prompt):
    model = "sonnet"
    template_dir = _DIR
    template_file = "analyze.md"
```

### 4. Use the registry

```python
from xprompt import PromptRegistry

registry = PromptRegistry(overrides=config.get("prompts", {}))
registry.register("reviewer.analyze", AnalyzeDocument)

prompt = registry.get("reviewer.analyze")
text = prompt.render(content=doc, criteria_text=criteria)
```

### 5. Optional autodiscovery addon

```python
from xprompt import PromptRegistry
from xprompt.addons.discovery import register_discovered

registry = PromptRegistry(overrides=config.get("prompts", {}))
register_discovered(registry, packages=["myapp"])  # opt-in
```

Discovery is optional. If you do not call it, registration stays fully manual.


## Inline body (no .md file)

```python
class Persona(Prompt):
    def body(self, **ctx):
        return "You are a senior technical reviewer."
```


## Blocks (reusable fragments)

```python
class ScoringRubric(Prompt):
    is_block = True
    template_file = "scoring_rubric.md"
```

`is_block = True` hides it from `registry.all()` by default. Same render, same versioning.


## Composition (JSX-style)

`body()` returns a list. Strings, Prompt instances, `None`. Nested lists flatten recursively. `None` is skipped.

```python
class Review(Prompt):
    model = "opus"

    def body(self, **ctx):
        return [
            Persona(),
            ScoringRubric(),
            "## Document\n\n" + ctx["content"],
            OutputFormat(),
            Constraints(),
        ]
```


## Composition (template-style)

For text-heavy prompts, use a Markdown template with `{{ blocks.ClassName }}` placeholders:

```python
class Review(Prompt):
    model = "opus"
    blocks = [ScoringRubric, Constraints]
    template_file = "review.md"
```

```markdown
---
description: Full document review
---
{{ blocks.ScoringRubric }}

## Document

{{ content }}

{{ blocks.Constraints }}
```


## Parametric blocks

```python
class Header(Prompt):
    def __init__(self, title: str, subtitle: str):
        super().__init__()
        self.title = title
        self.subtitle = subtitle

    def body(self, **ctx):
        return f"## {self.title}\n\n{self.subtitle}"
```


## Conditional composition

```python
def body(self, **ctx):
    return [
        ScoringRubric(),
        TechnicalCriteria() if ctx["doc_type"] == "technical" else None,
        LegalCriteria()     if ctx["doc_type"] == "legal" else None,
        OutputFormat(),
    ]
```


## Variants and A/B testing

```python
class Analyze(Prompt):
    model = "sonnet"
    template_file = "analyze.md"

class AnalyzeCoT(Analyze):
    """Chain-of-thought variant."""
    template_file = "analyze_cot.md"
```

Activate without code change:

```yaml
# config.yml
prompts:
  reviewer.analyze: AnalyzeCoT
```

Revert = delete the line.


## NodeSet (structured data items)

For prompt sections that are collections of items (rules, criteria, levels), not prose:

```python
from xprompt import NodeSet

class EvalCriteria(NodeSet):
    data_file = "criteria.yml"
    sort_key = "priority"
```

```yaml
# criteria.yml
- id: completeness
  label: Completeness
  content: Does the document cover all required topics?
  priority: 1

- id: accuracy
  label: Accuracy
  content: Are claims supported by evidence?
  priority: 2
```

Output:

```
1. **Completeness** -- Does the document cover all required topics?

2. **Accuracy** -- Are claims supported by evidence?
```

Override `nodes()` to filter, `render_node()` to change formatting. Inline items via `items = [...]` for small lists.


## Decorators

Standard Python class decorators work on prompts:

```python
@log_render(logger)
@validate_json_output
class Review(Prompt):
    ...
```


## Introspection

```python
for name, cls in registry.all():
    print(f"{name:40s}  model={cls.model or '-':8s}")
```


## Testing

```python
def test_review_renders():
    text = Review().render(content="test doc")
    assert "## Scoring" in text
    assert "{{ " not in text   # no unresolved variables
```

Import, call, assert. No fixtures, no registry setup, no filesystem mocking.


## File layout

```
xprompt/
  __init__.py       # exports: Prompt, NodeSet, PromptRegistry, prompt
  prompt.py         # Prompt, NodeSet, _flatten()
  registry.py       # PromptRegistry + @prompt decorator
```

Your app colocates prompts with domain modules:

```
myapp/
  analysis/
    prompts/
      __init__.py          # AnalyzeDocument(Prompt) with template_dir = _DIR
      analyze.md           # Jinja2 template
  synthesis/
    prompts/
      __init__.py          # Synthesize(Prompt)
      synthesize.md
  prompts.py               # create_registry() -- thin aggregator
```


## Design decisions

- **Classes, not files, are the primary identity.** A prompt is a Python object. The `.md` file is its template, not its identity.
- **Two composition modes.** JSX-style (`body()` returns a list) for programmatic control. Template-style (`blocks` + `.md`) for text-heavy prompts.
- **`_flatten()` is the entire renderer.** 15 lines. Handles str, list, Prompt, None.
- **Config overrides for variant switching.** Map dotted names to class names. Empty by default.
- **Strict undefined.** Missing Jinja2 variables raise immediately. No silent `""` substitution.
