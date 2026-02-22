# xprompt -- Cheatsheet

## Define a prompt

```python
class AnalyzeDocument(Prompt):
    model = "sonnet"
    template_file = "analyze.md"
```

## Define a block

```python
class ScoringRubric(Prompt):
    is_block = True
    template_file = "_blocks/scoring_rubric.md"
```

## Inline body (no .md file)

```python
class Persona(Prompt):
    def body(self, **ctx):
        return "You are a senior technical reviewer."
```

## Compose (JSX-style)

```python
class Evaluate(Prompt):
    def body(self, **ctx):
        return [Persona(), ScoringRubric(), "## Data\n\n" + ctx["data"]]
```

## Compose (template-style)

```python
class Evaluate(Prompt):
    blocks = [ScoringRubric, Constraints]
    template_file = "evaluate.md"
```
```markdown
{{ blocks.ScoringRubric }}
## Data
{{ data }}
{{ blocks.Constraints }}
```

## Parametric block

```python
class Header(Prompt):
    def __init__(self, title: str, subtitle: str):
        super().__init__()
        self.title = title
        self.subtitle = subtitle

    def body(self, **ctx):
        return f"## {self.title} -- {self.subtitle}"
```

## Conditional

```python
def body(self, **ctx):
    return [
        ScoringRubric(),
        TechnicalCriteria() if ctx["doc_type"] == "technical" else None,
        EvalFramework(),
    ]
```

## Loop

```python
def body(self, **ctx):
    return [FindingGroup(cat, items) for cat, items in ctx["groups"].items()]
```

## Variant / A/B test

```python
class EvaluateCoT(Evaluate):
    template_file = "evaluate_cot.md"
```
```yaml
# config.yml
prompts:
  evaluator.evaluate: EvaluateCoT
```

## Registry

```python
reg = PromptRegistry(overrides=cfg.get("prompts", {}))
reg.register("reviewer.analyze", AnalyzeDocument)
text = reg.get("reviewer.analyze").render(content=doc, criteria_text=criteria)
```

## Decorator

```python
def log_render(logger):
    def decorator(cls):
        orig = cls.render
        def render(self, **kw):
            t0 = time.monotonic()
            r = orig(self, **kw)
            logger.info("rendered", prompt=cls.__name__, ms=int((time.monotonic()-t0)*1000))
            return r
        cls.render = render
        return cls
    return decorator
```

## NodeSet -- items from YAML

```python
class EvalCriteria(NodeSet):
    data_file = "_data/eval_criteria.yml"
    sort_key = "priority"
```
```yaml
# _data/eval_criteria.yml
- id: completeness
  label: Completeness
  content: Does the document cover all required topics?
  priority: 1
- id: accuracy
  label: Accuracy
  content: Are claims supported by evidence?
  priority: 2
```

## NodeSet -- inline items

```python
class Constraints(NodeSet):
    items = [
        {"id": "sum", "content": "Scores must sum to 100"},
        {"id": "no_invent", "content": "Do not invent evidence"},
    ]
    def render_node(self, index, node, **ctx):
        return f"- {node['content']}"
```

## NodeSet -- filter by context

```python
class DomainRules(NodeSet):
    data_file = "_data/domain_rules.yml"
    def nodes(self, **ctx):
        doc_type = ctx.get("doc_type", "")
        return [n for n in super().nodes(**ctx) if doc_type in n.get("types", [])]
```

## NodeSet in composition

```python
def body(self, **ctx):
    return [Persona(), ScoringLevels(), "## Data\n\n" + ctx["data"], Constraints()]
```

## Test

```python
def test_evaluate():
    text = Evaluate().render(data="findings...")
    assert "## Scoring" in text
    assert "{{ " not in text
```

## Meta

```python
prompt = reg.get("reviewer.analyze")
prompt.meta()  # {"description": "...", "model": "sonnet"}
```
