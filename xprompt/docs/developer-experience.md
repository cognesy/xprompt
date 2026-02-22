# xprompt -- Developer Experience

Target developer experience across common scenarios.


## Using a prompt in a service (90% of interactions)

```python
class ReviewService:
    def __init__(self, prompts: PromptRegistry):
        self.prompts = prompts

    def review_document(self, doc_id: int, criteria: list[dict]):
        prompt = self.prompts.get("reviewer.analyze")
        text = prompt.render(criteria_text=format_criteria(criteria), content=doc.content_text)
        model = prompt.model  # "sonnet"
        result = self.llm.call(model=model, prompt=text)
```

`.get()`, `.render()`, `.model`. The service doesn't know how the prompt is
built.


## Defining prompts

**Simple (no composition):**

```python
class ClassifyPaths(Prompt):
    """Classify files by path into categories."""
    model = "haiku"
    template_file = "classify_paths.md"
```

**Block (reusable fragment):**

```python
class ScoringRubric(Prompt):
    """Five-level scoring rubric."""
    is_block = True
    template_file = "_blocks/scoring_rubric.md"
```

A block is a prompt with `is_block = True`. Same render, same versioning.
The flag is for registry filtering only.


## Variants and A/B testing

```python
class Evaluate(Prompt):
    model = "opus"
    template_file = "evaluate.md"

class EvaluateCoT(Evaluate):
    """Variant: chain-of-thought before JSON output."""
    template_file = "evaluate_cot.md"
    # inherits model, blocks
```

```yaml
# config.yml -- activate variant, zero code changes
prompts:
  evaluator.evaluate: EvaluateCoT
```

Revert = delete the line. Works for blocks too:

```yaml
prompts:
  _blocks.eval_framework: FiveLenses   # swaps across all prompts that use it
```


## Decorators

```python
@validate_json_output
@log_render(log)
class Evaluate(Prompt):
    ...
```

Impossible with file-based templates. With classes, it's standard Python.


## Introspection and testing

```python
for name, prompt in registry.all():
    print(f"{name:40s}  model={prompt.model:8s}")
```

```python
def test_evaluate_renders():
    text = Evaluate().render(document_name="API Spec", review_data="...")
    assert "## Scoring" in text
    assert "{{ " not in text
```

Import, call, assert. No fixtures.


---


## Composition: templates vs components

The key design decision. Two mental models.


### Template model (Jinja2 includes)

HTML-templates style. Composition via string interpolation.

```markdown
{% include "_blocks/persona/technical_reviewer.md" %}
{% include "_blocks/domain/scoring_rubric.md" %}
{% if doc_type in ["api_spec", "architecture", "integration"] %}
{% include "_blocks/domain/technical_standards.md" %}
{% endif %}
{{ review_data }}
{% for block in extra_blocks %}
{% include block %}
{% endfor %}
```

Template declares what, where, and when. Python code just calls
`prompt.render(**ctx)`.


### Component model (JSX-style)

`body()` returns a tree of renderables. Strings, blocks, `None` (skipped).
Flat list -> joined with `\n\n`.

```python
class Evaluate(Prompt):
    model = "opus"

    def body(self, **ctx):
        return [
            TechnicalReviewer(),
            ScoringRubric(),
            TechnicalStandards() if ctx["doc_type"] in ("api_spec", "architecture") else None,
            "## Review Data\n\n" + ctx["review_data"],
            EvalFramework(),
            JsonReport(),
            EvidenceGrounding(),
        ]
```

Python declares what, where, and when. No template language.


### Blocks are callables that return strings

Inline:

```python
class ScoringRubric(Prompt):
    def body(self, **ctx):
        return """## Scoring Rubric
- L0 -- Not Assessed: Insufficient evidence.
- L1 -- Basic: Topic addressed, coverage shallow.
- L2 -- Adequate: Covered consistently. Key points present.
- L3 -- Thorough: Comprehensive with supporting evidence.
- L4 -- Exemplary: Best-in-class. Evidence-backed, actionable."""
```

External (long text stays in Markdown):

```python
class ScoringRubric(Prompt):
    template_file = "_blocks/scoring_rubric.md"
```

Mix freely. Short blocks inline, long templates external.


### Nesting

```python
class AnalyticalSection(Prompt):
    def body(self, **ctx):
        return [
            "## Evaluation Framework",
            EvalLenses(),
            "## Output Format",
            JsonReport(),
            "## Constraints",
            EvidenceGrounding(),
            NoInventedEvidence(),
        ]

class Evaluate(Prompt):
    def body(self, **ctx):
        return [
            TechnicalReviewer(),
            SectionHeader(ctx["doc_name"], ctx["doc_desc"]),
            ScoringRubric(),
            ReviewData(ctx["data"]),
            AnalyticalSection(),        # expands recursively
        ]
```


### Parametric blocks

```python
class SectionHeader(Prompt):
    def __init__(self, title: str, description: str):
        self.title = title
        self.description = description

    def body(self, **ctx):
        return f"## {self.title}\n\n{self.description}"

class FewShot(Prompt):
    def __init__(self, *examples: tuple[str, str]):
        self.examples = examples

    def body(self, **ctx):
        return [f"Input: {i}\nOutput: {o}" for i, o in self.examples]
```

Props, not template variables.


### Conditional composition

```python
class Evaluate(Prompt):
    def body(self, **ctx):
        doc_type = ctx["doc_type"]
        return [
            TechnicalReviewer(),
            ScoringRubric(),
            TechnicalStandards() if doc_type in ("api_spec", "architecture") else None,
            LegalStandards()     if doc_type == "contract" else None,
            SecurityChecklist()  if doc_type == "security" else None,
            ReviewData(ctx["data"]),
            EvalFramework(),
            JsonReport(),
        ]
```


### Loop composition

```python
class ReviewData(Prompt):
    def __init__(self, findings_by_category: dict[str, list]):
        self.findings = findings_by_category

    def body(self, **ctx):
        return [
            FindingGroup(category, findings)
            for category, findings in self.findings.items()
            if findings
        ]
```


### The render contract

```python
class Prompt:
    def render(self, **ctx) -> str:
        raw = self.body(**ctx)
        return self._flatten(raw)

    def _flatten(self, node) -> str:
        if node is None:
            return ""
        if isinstance(node, str):
            return node
        if isinstance(node, Prompt):
            return node.render()
        if isinstance(node, list):
            parts = [self._flatten(n) for n in node]
            return "\n\n".join(p for p in parts if p)
        return str(node)
```

~15 lines. The entire rendering engine.


### Side by side

| | Jinja2 templates | Prompt components |
|-|-----------------|-------------------|
| Composition | `{% include "path" %}` | `MyBlock()` in a list |
| Conditionals | `{% if x %}...{% endif %}` | `MyBlock() if x else None` |
| Loops | `{% for b in blocks %}{% include b %}{% endfor %}` | `[MyBlock(b) for b in items]` |
| Parameters | `{{ var }}` in template | Constructor args |
| Nesting | Include inside include | Component inside component |
| Type safety | None | Full |
| Where's the text | `.md` file (always) | Inline, `.md` file, or both |
| Rendering engine | Jinja2 (~10K lines) | `_flatten()` (~15 lines) |


---


## Summary

| Task | What you do |
|------|-------------|
| Use a prompt | `prompts.get("name").render(**kwargs)` |
| Read the template | Open the `.md` file |
| Change the wording | Edit the `.md` file |
| Add a variant | Subclass, override `template_file` or `body()` |
| Activate a variant | One line in config |
| Compose (template) | `{% include %}` in `.md` |
| Compose (component) | Return list from `body()` |
| Add behavior | Decorator on the class |
| Debug | `registry.all()`, Python introspection |
| Test | Import, render, assert |
