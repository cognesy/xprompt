# xprompt -- Structured Nodes

## Problem

Some prompt components aren't text blocks. They're **collections of
individually manageable items** -- rules, criteria, levels, constraints --
where you need to:

- Add or remove a single item without rewriting the whole section
- Reorder items by priority or category
- Filter items by context (e.g. different rules for different document types)
- Store items as data (YAML), not embedded in Python or Markdown

A complex evaluation prompt illustrates this. Three of its five sections are item
collections, not prose:

| Section | Type | Items | Manage as... |
|---------|------|-------|--------------|
| Persona | text | 1 sentence | `.md` or inline string |
| Scoring Rubric | **items** | 5 levels with id/label/description | YAML |
| Evaluation Lenses | **items** | 9 lenses, each a question | YAML |
| Output Schema | text | JSON schema blob | `.md` or inline string |
| Constraints | **items** | 4 individual rules | YAML |

Today all five are one 90-line text wall. Adding lens #10 means editing a
paragraph. Removing constraint #3 means editing a paragraph. Reordering lenses
by priority is impossible without rewriting.


## Mental model

A prompt is a **tree**. Leaf nodes are either:

- **Text** -- a paragraph, a section header, a Markdown block
- **Data items** -- individual rules/levels/lenses loaded from a YAML file

Each data item has:
- `id` -- stable identifier
- `label` -- human-readable name (optional, falls back to id)
- `content` -- the text payload
- `children` -- nested sub-items (optional)
- Arbitrary metadata -- `priority`, `category`, `tags`, etc.

A **renderer** knows how to turn items into text. The default renders
numbered lists. Override `render_node()` for bullets, paragraphs, tables,
or anything else.


## NodeSet -- the building block

`NodeSet` is a `Prompt` subclass. It loads items from YAML (or inline) and
renders them. It composes into the prompt tree like any other block.

```python
from xprompt import NodeSet

class EvalLenses(NodeSet):
    data_file = "_data/eval_lenses.yml"
    sort_key = "priority"
```

YAML (`_data/eval_lenses.yml`):

```yaml
- id: completeness
  label: Completeness
  content: Does the document cover all required topics? Are there gaps?
  priority: 1
  category: foundation

- id: accuracy
  label: Accuracy
  content: Are claims factually correct and supported by evidence?
  priority: 2
  category: foundation

- id: consistency
  label: Consistency
  content: Does execution match stated methodology? Are outcomes consistent?
  priority: 3
  category: quality

- id: depth
  label: Depth of Analysis
  content: Is the analysis surface-level or does it address root causes?
  priority: 4
  category: quality

- id: measurability
  label: Measurability
  content: Are metrics defined? Are thresholds and targets specified?
  priority: 5
  category: quality

- id: trends
  label: Trend Awareness
  content: Is performance tracked over time? Are deviations detected proactively?
  priority: 6
  category: insight

- id: benchmarking
  label: Benchmarking
  content: Is the work compared against standards or industry norms?
  priority: 7
  category: insight

- id: actionability
  label: Actionability
  content: Are recommendations concrete, prioritized, and feasible?
  priority: 8
  category: outcome

- id: innovation
  label: Innovation
  content: Are novel approaches or automation used where appropriate?
  priority: 9
  category: advanced
```

Default output:

```
1. **Completeness** -- Does the document cover all required topics? Are there gaps?

2. **Accuracy** -- Are claims factually correct and supported by evidence?

...

9. **Innovation** -- Are novel approaches or automation used where appropriate?
```

Adding lens #10: add a YAML entry. Reorder: change `priority`. Remove: delete
the entry. No text editing. Clean git diff.


## API

```python
class NodeSet(Prompt):
    data_file: str | None       # path to YAML file (relative to prompts root)
    sort_key: str | None        # metadata key to sort by
    items: list[dict] | None    # inline alternative to data_file

    def nodes(self, **ctx) -> list[dict]:
        """Load, sort, return nodes. Override to filter/transform."""

    def render_node(self, index: int, node: dict, **ctx) -> str:
        """Render one node. Override for custom format."""

    def body(self, **ctx) -> list[str]:
        """Calls nodes() then render_node() per item."""
```

Three override points:
- `nodes()` -- filter, augment, or replace the item list
- `render_node()` -- change how each item becomes text
- `body()` -- full control (rarely needed)


## Operations on items

### Add an item

Add to YAML:

```yaml
- id: stakeholder_alignment
  label: Stakeholder Alignment
  content: Are stakeholders regularly engaged and aligned on progress?
  priority: 3
  category: foundation
```

Git diff: one block added. Nothing else touched.


### Remove an item

Delete from YAML. Git diff: one block removed.


### Reorder

Change `priority` values. Or change `sort_key` on the class.


### Filter by context

Override `nodes()`:

```python
class EvalLenses(NodeSet):
    data_file = "_data/eval_lenses.yml"
    sort_key = "priority"

    def nodes(self, **ctx):
        all_nodes = super().nodes(**ctx)
        # For basic reviews, skip advanced lenses
        if ctx.get("review_depth", "full") == "basic":
            return [n for n in all_nodes if n.get("category") != "advanced"]
        return all_nodes
```


### Custom rendering

Override `render_node()`:

```python
class Constraints(NodeSet):
    data_file = "_data/constraints.yml"

    def render_node(self, index, node, **ctx):
        return f"- {node['content']}"
```

Output: bullet list instead of numbered.


### Type-specific items

Pass context, filter in `nodes()`:

```python
class DomainRules(NodeSet):
    data_file = "_data/domain_rules.yml"

    def nodes(self, **ctx):
        doc_type = ctx.get("doc_type", "")
        return [n for n in super().nodes(**ctx) if doc_type in n.get("types", [])]
```

```yaml
- id: api_standards
  content: API endpoints must follow RESTful conventions and include error schemas
  types: [api_spec, integration]

- id: data_traceability
  content: All data transformations must have bidirectional traceability
  types: [data_migration]
```


## Nested children

Items can have sub-items:

```yaml
- id: output_schema
  label: Output Fields
  children:
    - id: document
      content: '"document": "<document_name>"'
    - id: summary
      content: '"summary": "<3-5 sentence overview>"'
    - id: score_breakdown
      label: score_breakdown
      children:
        - id: completeness
          content: '"completeness": <integer 0-100>'
        - id: accuracy
          content: '"accuracy": <integer 0-100>'
```

Default renderer indents children:

```
1. **Output Fields**
   - "document": "<document_name>"
   - "summary": "<3-5 sentence overview>"
   - score_breakdown
```

Override `render_node()` for deeper nesting or tree rendering.


## Composing into the prompt tree

NodeSet is a Prompt. It composes like any other block:

```python
class Evaluate(Prompt):
    model = "opus"

    def body(self, **ctx):
        return [
            Persona(),
            "## Document\n\n" + ctx["doc_name"],
            "## Scoring Rubric",
            ScoringLevels(),             # NodeSet from levels.yml
            "## Review Data\n\n" + ctx["data"],
            "## Evaluation Framework\n\nReason through each lens:",
            EvalLenses(),                # NodeSet from lenses.yml
            "## Constraints",
            Constraints(),               # NodeSet from constraints.yml
            OutputSchema(),              # text block (.md file)
        ]
```

Text blocks and NodeSets interleave freely. The tree renders top-down.
NodeSets expand into their items. `_flatten()` joins everything.


## Concrete decomposition: evaluation prompt

Before: 1 file, 90 lines, monolithic text.

After:

| Component | Type | Source | Items | Lines |
|-----------|------|--------|-------|-------|
| Persona | `Prompt` (inline) | -- | -- | 3 |
| ScoringLevels | `NodeSet` | `_data/scoring_levels.yml` | 5 | ~20 |
| EvalLenses | `NodeSet` | `_data/eval_lenses.yml` | 9 | ~40 |
| OutputSchema | `Prompt` | `_blocks/json_report.md` | -- | ~25 |
| Constraints | `NodeSet` | `_data/constraints.yml` | 4 | ~10 |
| **Evaluate** | `Prompt` | entry point | -- | ~15 |

Total: 6 files, each small and focused. Individually editable, versionable,
testable.

```yaml
# _data/constraints.yml
- id: score_sum
  content: Score values must sum to exactly 100
  category: schema

- id: priority_items_count
  content: priority_items must contain 3 to 5 items, ordered from highest to lowest impact
  category: schema

- id: no_invented_evidence
  content: Do not invent evidence. Every claim must trace to content in the review data
  category: grounding

- id: no_extra_output
  content: Do not produce markdown, prose, or any output outside the JSON object
  category: format
```

Adding a constraint: one YAML entry. Removing: delete it. Reordering: sort
by category or add priority. Swapping the entire set: subclass + config
override, same as any prompt variant.


## Inline items (no YAML file)

For small, stable lists that don't need external management:

```python
class ScoringLevels(NodeSet):
    sort_key = "level"
    items = [
        {"id": "L0", "label": "L0 -- Not Assessed", "content": "Insufficient evidence.", "level": 0},
        {"id": "L1", "label": "L1 -- Basic", "content": "Topic addressed, coverage shallow.", "level": 1},
        {"id": "L2", "label": "L2 -- Adequate", "content": "Covered consistently. Key points present.", "level": 2},
        {"id": "L3", "label": "L3 -- Thorough", "content": "Comprehensive with supporting evidence.", "level": 3},
        {"id": "L4", "label": "L4 -- Exemplary", "content": "Best-in-class. Evidence-backed, actionable.", "level": 4},
    ]

    def render_node(self, index, node, **ctx):
        return f"- {node['label']}: {node['content']}"
```

Same API, no file dependency. Graduate to YAML when the list grows or needs
external management.


## Design properties

- **NodeSet is a Prompt.** No new concepts. Same `render()`, same
  `_flatten()`, same composition, same registry, same variants.
- **Nodes are dicts.** No dataclass, no model. A node is `{"id": "...", ...}`.
  Metadata is arbitrary -- only the renderer interprets it.
- **Three override points.** `nodes()` for data, `render_node()` for format,
  `body()` for full control.
- **YAML is optional.** Inline `items` for small lists. YAML for externally
  managed collections. Same API.
- **Git-friendly.** Adding/removing YAML entries produces clean, reviewable
  diffs. No text reformatting noise.
