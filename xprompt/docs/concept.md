# xprompt -- Concept

## Problem

Prompts embedded as inline strings inside service modules create several problems:

- **No visibility.** Prompts are buried in Python code. Reviewing or editing a prompt
  requires navigating to the right method, finding the f-string, and mentally
  separating Jinja/format variables from Python logic.
- **No versioning.** Changing a prompt means changing Python source. There is no way
  to keep two versions side-by-side, compare outputs, or roll back without git
  archaeology.
- **No A/B testing.** Running an experiment (e.g. "does adding chain-of-thought
  improve output quality?") requires a code change, a run, and another code change
  to revert.
- **No separation of concerns.** The person tuning prompts must touch the same files as
  the person writing pipeline logic.

## Goal

A micro-library (~150-200 lines) that:

1. Stores each prompt as a standalone Markdown file with YAML front-matter.
2. Organizes prompts under a namespace-style addressing scheme
   (`reviewer.analyze`).
3. Renders prompts via Jinja2.
4. Supports multiple versions per prompt.
5. Lets config select which version is active -- no code change needed.
6. Has zero coupling to LLM clients, Rich, or any framework.

Dependencies: `jinja2`, `python-frontmatter` (PyYAML wrapper, zero transitive deps
beyond pyyaml).


## Prompt File Format

Each prompt is a Markdown file. YAML front-matter carries metadata. Body is the
Jinja2 template.

```markdown
---
description: Analyze document against evaluation criteria
model: sonnet
version: v1
---
Analyze this document against the criteria below.
For each criterion where you find evidence (positive or negative), extract a finding.

CRITERIA:
{{ criteria_text }}

DOCUMENT:
{{ content }}

For each finding:
- criterion_code: the criterion code (e.g., SEC-003)
- observation: what you observed
- score: -1.0 to +1.0
- evidence_quote: short excerpt
- location_hint: section or page reference

Return empty findings list if no relevant evidence found.
```

Front-matter fields:

| Field | Required | Purpose |
|-------|----------|---------|
| description | no | Human-readable summary |
| model | no | Suggested model (informational, not enforced) |
| version | yes | Version identifier for this variant |
| Any other key | no | Available as `meta.<key>` in caller code |


## Directory Layout and Namespacing

Prompt identity = directory path. Each prompt gets its own directory. Files inside
that directory are versions.

```
prompts/
  reviewer/
    analyze/
      default.md              # the production version
      chain_of_thought.md     # experimental: adds CoT reasoning
    analyze_v0/
      default.md              # archived original (read-only, kept for reference)
  summarizer/
    synthesize/
      default.md
  evaluator/
    evaluate/
      default.md
      confidence_dist.md      # variant: outputs probability distribution
  classifier/
    classify_content/
      default.md
    classify_paths/
      default.md
  curator/
    curate_index/
      default.md
```

Prompt name = directory path relative to prompts root, with `/` replaced by `.`.
Full address: `reviewer.analyze`. Version = filename (minus `.md`).

The `default.md` file is always the production version. No ambiguity, no
resolution logic, no markers in front-matter.

Caller code:

```python
from xprompt import PromptRegistry

prompts = PromptRegistry("prompts/")
text = prompts.render("reviewer.analyze", criteria_text=criteria, content=doc)
meta = prompts.meta("reviewer.analyze")  # front-matter dict
```


## Versioning

### Design principles

- **Prompt name is a directory, not a file.** Stable, never renamed. Code
  references the directory path. Git history of the directory shows the full
  evolution.
- **Versions are files, with descriptive names.** `chain_of_thought.md` tells
  you what's different. `v2.md` does not. File names describe the variant's
  hypothesis, not a sequence number.
- **`default.md` is always the active version.** Convention, not configuration.
  There is no resolution logic, no "highest wins", no markers. The file named
  `default.md` is what runs in production. Period.
- **Switching versions = one config line.** An override in config points the
  prompt name to a different filename. No file renames, no code changes.
- **Adding a variant never touches the default.** You create a new `.md` file
  in the same directory. The default is untouched. Git diff is clean.


### How version switching works

Without any config override, the registry loads `default.md` from the prompt's
directory. To activate a variant:

```yaml
# config.yml
prompts:
  reviewer.analyze: chain_of_thought
  # all other prompts use default.md
```

The registry sees the override, loads `chain_of_thought.md` instead of
`default.md` from `prompts/reviewer/analyze/`.

To revert: remove the line. `default.md` takes over again.


### Where to configure

Version overrides live in your existing config file, not a separate registry file.
Rationale:

- **One config file.** Prompt overrides belong with the rest of the pipeline
  configuration, not in a second file that can drift.
- **Minimal surface.** The `prompts:` section is empty by default. It only
  contains entries when something is overridden. Zero lines = everything runs
  on defaults.
- **Operational.** When debugging, you check one file to see what prompts are
  non-default. No need to cross-reference a separate registry.

```yaml
# config.yml -- only overrides, not a full inventory
prompts:
  reviewer.analyze: chain_of_thought
  evaluator.evaluate: confidence_dist
```

Alternative considered and rejected:

| Approach | Why not |
|----------|---------|
| Separate `prompts.yml` registry | Second file to maintain. Drifts from config. No benefit -- the override map is 0-10 lines. |
| Per-directory config (e.g. `prompts/reviewer/analyze/.active`) | Scattered config. Must scan the entire tree to know what's active. Defeats the "one place to look" property. |
| Front-matter `default: true` marker | Requires parsing all version files to find the default. Ambiguous if two files claim default. `default.md` as a filename is simpler and unambiguous. |


### Comparison with other approaches

| Approach | Prompt identity | Version identity | Default | Selection | Git behavior |
|----------|----------------|-----------------|---------|-----------|-------------|
| Banks | Filename stem | Filename suffix (`name.v1.jinja`) | Version `"0"` | Code: `get(name, version)` | Rename = lost blame |
| Semantic Kernel (old) | Directory path | Top-level version dirs | Implicit (latest dir) | Code: load specific dir | Full copies across dirs |
| Semantic Kernel (new) | Single YAML file | None (one file) | N/A | N/A | Clean |
| prompt-serve | UUID in YAML | Git history | HEAD | API reads tag/commit | Native git |
| LaunchDarkly | Hosted key | Server-side counter | Feature flag | Runtime flag eval | N/A |
| **xprompt** | **Directory path** | **Descriptive filename** | **`default.md` convention** | **Config override** | **Add file = clean diff** |

Key differences from Banks: identity is a directory (stable, never renamed), not a
filename that must be parsed. Versions have descriptive names, not opaque sequence
numbers. Default is a filename convention, not metadata. Selection is config-driven,
not code-driven.


## A/B Testing Workflow

1. Author writes `chain_of_thought.md` in `prompts/reviewer/analyze/`.
   Does not touch `default.md`.
2. In config, add: `reviewer.analyze: chain_of_thought`.
3. Run pipeline. Compare results against baseline.
4. If the variant wins:
   - Rename current `default.md` to a descriptive archive name (e.g. `baseline_v1.md`).
   - Rename `chain_of_thought.md` to `default.md`.
   - Remove the config override.
   - This is the one case where files are renamed. It's intentional: the winning
     variant becomes the new default. Git tracks the rename.
5. If the variant loses: delete `chain_of_thought.md`, remove config override.
6. Commit.

No code changes at any step. Config changes are 0-1 lines.


## Prompt File Format

Each prompt is a Markdown file. YAML front-matter carries metadata. Body is the
Jinja2 template.

```markdown
---
description: Analyze document against evaluation criteria
model: sonnet
---
Analyze this document against the criteria below.
For each criterion where you find evidence (positive or negative), extract a finding.

CRITERIA:
{{ criteria_text }}

DOCUMENT:
{{ content }}

For each finding:
- criterion_code: the criterion code (e.g., SEC-003)
- observation: what you observed
- score: -1.0 to +1.0
- evidence_quote: short excerpt
- location_hint: section or page reference

Return empty findings list if no relevant evidence found.
```

Front-matter fields:

| Field | Required | Purpose |
|-------|----------|---------|
| description | yes | What this prompt does (one line) |
| model | no | Suggested model tier (informational, not enforced) |
| Any other key | no | Available as `meta.<key>` in caller code |

No `version` field in front-matter. The version is the filename. No `default`
marker. The default is the file named `default.md`.


## Composition

### The problem

A complex prompt can be ~90 lines with at least 5 distinct concerns:

1. **Persona** -- "You are a senior technical reviewer..."
2. **Domain knowledge** -- scoring rubric definition, what each level means
3. **Analytical framework** -- the evaluation lenses (completeness, accuracy, depth...)
4. **Output schema** -- JSON structure with fields, types, constraints
5. **Constraints** -- "scores must sum to 100", "do not invent evidence"

Every one of these is independently editable. The rubric applies to all
document types. The analytical framework might get a variant for A/B testing. The
output schema changes when you add a field. But today they're welded into one
monolithic string.

As prompts mature, they accumulate sections for error handling, style guidance,
domain context, few-shot examples. A 10K-character prompt with inline edits
becomes unreadable and un-diffable.


### Design: blocks as first-class prompts

Blocks are not a separate concept. They are prompts -- same `.md` format, same
front-matter, same versioning, same directory structure. The only difference is
convention: blocks live under a `_blocks/` namespace (underscore prefix signals
"not a standalone prompt"), and they are composed into other prompts via Jinja2
`{% include %}`.

```
prompts/
  _blocks/
    persona/
      technical_reviewer/
        default.md
    domain/
      scoring_rubric/
        default.md
      eval_framework/
        default.md
        nine_lenses.md        # variant: expanded 9-lens framework
        five_lenses.md        # variant: simplified 5-lens
    format/
      json_report/
        default.md
    constraints/
      evidence_grounding/
        default.md
  evaluator/
    evaluate/
      default.md              # composes blocks via {% include %}
  reviewer/
    analyze/
      default.md
```

Why `_blocks/` and not `blocks/`?
- Underscore prefix is a universal "internal/private" convention (Python, Sass,
  filesystem). Signals: "these are building blocks, not entry points."
- The registry can optionally skip `_blocks/` when listing available prompts
  (show entry points only), while still resolving includes from them.


### How composition works

Jinja2 `{% include %}` handles everything. No custom machinery.

**`prompts/evaluator/evaluate/default.md`:**
```markdown
---
description: Full document evaluation
model: opus
---
{% include "_blocks/persona/technical_reviewer/default.md" %}

## Document Under Review

Document: {{ document_name }}

Description and scope:
{{ document_description }}

{% include "_blocks/domain/scoring_rubric/default.md" %}

## Review Data

{{ review_data }}

{% include "_blocks/domain/eval_framework/default.md" %}

{% include "_blocks/format/json_report/default.md" %}

{% include "_blocks/constraints/evidence_grounding/default.md" %}
```

**`prompts/_blocks/domain/scoring_rubric/default.md`:**
```markdown
---
description: Five-level scoring rubric
---
## Scoring Rubric

Documents are scored on a five-level scale. Levels are cumulative.

- L0 -- Not Assessed: Insufficient evidence to form a view.
- L1 -- Basic: The topic is addressed but coverage is shallow or inconsistent.
- L2 -- Adequate: Covered consistently. Key points are present.
- L3 -- Thorough: Comprehensive coverage with supporting evidence.
- L4 -- Exemplary: Best-in-class. Clear, evidence-backed, actionable.
```

Each block is a standalone file. Own git history. Own versioning. Edit the
rubric without touching the evaluation prompt or the analytical framework.


### Dynamic composition

Sometimes the set of blocks varies at runtime. Two mechanisms, both native Jinja2:

**1. Conditional includes (static set, dynamic selection):**
```markdown
{% include "_blocks/persona/technical_reviewer/default.md" %}
{% if doc_type in ["api_spec", "architecture", "integration"] %}
{% include "_blocks/domain/technical_standards.md" %}
{% else %}
{% include "_blocks/domain/general_standards.md" %}
{% endif %}
```

**2. Loop includes (caller passes block list):**
```python
text = prompts.render("evaluator.evaluate",
    document_name="API Design Spec",
    review_data=data,
    extra_blocks=[
        "_blocks/domain/technical_standards.md",
    ],
)
```

```markdown
{# in the template #}
{% for block in extra_blocks %}
{% include block %}
{% endfor %}
```

Both are standard Jinja2. Zero custom code in xprompt.


### Block resolution and versioning

Since blocks are regular prompts, config overrides work the same way:

```yaml
# config.yml -- swap eval framework to 5-lens variant
prompts:
  _blocks.domain.eval_framework: five_lenses
```

When the evaluation prompt does `{% include "_blocks/domain/eval_framework/default.md" %}`,
the registry's Jinja2 loader intercepts the include and resolves it through the
same override logic: check config, if overridden load the variant filename, else
load `default.md`.

This means you can A/B test a block across all prompts that include it, with one
config line. Change the analytical framework everywhere at once, or pin one
prompt to use the old version.

**Implementation note:** this requires a custom Jinja2 loader that understands
the directory-per-prompt convention and config overrides. Roughly 20-30 lines --
subclass `jinja2.BaseLoader`, override `get_source()` to resolve
`_blocks/domain/eval_framework/default.md` through the override map.


### Why not front-matter-driven composition?

Alternative considered: declare blocks in front-matter instead of inline includes.

```yaml
---
compose:
  - _blocks.persona.technical_reviewer
  - _blocks.domain.scoring_rubric
  - _blocks.domain.eval_framework
---
(prompt body appended after composed blocks)
```

Rejected because:

- **Loses positioning control.** Blocks always prepend. But sometimes you need a
  block between two template sections (e.g. rubric before review data,
  constraints after output schema). Jinja2 `{% include %}` gives exact placement.
- **Loses conditional logic.** Front-matter is static YAML. Cannot express "include
  this block only for technical documents." Jinja2 `{% if %}` handles this natively.
- **Two composition mechanisms.** Front-matter for static blocks + Jinja2 for
  dynamic blocks = two systems to learn. Single mechanism (Jinja2 includes) is
  simpler.
- **Custom code.** Front-matter composition requires assembling text in Python.
  Jinja2 includes require zero custom code beyond the loader.


### Composition example: decomposing a complex prompt

Before: one 90-line inline string.

Proposed decomposition into 6 files:

| Block | Lines | Reusable by |
|-------|-------|-------------|
| `_blocks/persona/technical_reviewer` | ~3 | evaluator, reviewer |
| `_blocks/domain/scoring_rubric` | ~12 | evaluator, summarizer, any reporting |
| `_blocks/domain/eval_framework` | ~15 | evaluator only (for now) |
| `_blocks/format/json_report` | ~30 | evaluator only (for now) |
| `_blocks/constraints/evidence_grounding` | ~5 | evaluator, reviewer |
| `evaluator/evaluate` (the template) | ~15 | entry point -- composes the above |

The entry-point template drops from ~90 lines to ~15 lines of glue. Each block
is short, focused, independently editable, independently versionable.


## References: How Others Handle Composition

### Langfuse -- inline prompt references

Langfuse (hosted prompt management platform) uses a tag syntax to reference one
prompt from another:

```
@@@langfusePrompt:name=PromptName|version=1@@@
@@@langfusePrompt:name=PromptName|label=production@@@
```

Tags are resolved server-side when the prompt is fetched via SDK. Changing a
referenced prompt cascades to all dependents automatically.

**What we take:** the idea that composition should reference prompts by name,
not by file path. Our Jinja2 `{% include %}` paths are file-system paths, but
the custom loader resolves them through the same override logic as top-level
prompts -- so a block name like `_blocks.domain.scoring_rubric` is effectively
a stable reference, not a brittle path.

**What we skip:** hosted service, custom tag syntax. Jinja2 `{% include %}` is
a standard, well-understood mechanism. No proprietary syntax to learn.

Source: [Langfuse Prompt Composability](https://langfuse.com/changelog/2025-03-12-prompt-composability)


### Modular Prompt Design -- structured tags

The "Modular Prompt Architecture" pattern (OptizenApp, Deepak Sahoo) uses
HTML-like tags (`<role>`, `<requirements>`, `<output_format>`) to create
self-contained prompt modules saved as `.txt` files. Modules are chained via
placeholder injection: output of one module feeds `{placeholder}` in the next.

**What we take:** the decomposition principle -- break prompts into role,
requirements, output format, constraints. Our `_blocks/` directory structure
mirrors this taxonomy.

**What we skip:** the tag syntax. Markdown headings (`## Scoring Rubric`) serve
the same structural purpose without a custom parser. Jinja2 `{% include %}`
handles assembly without manual copy-paste between modules.

Source: [Modular Prompting - OptizenApp](https://optizenapp.com/ai-prompts/modular-prompting),
[Modular Prompt Design - Medium](https://medium.com/@deepakkumar05.it/modular-prompt-design-building-blocks-over-monoliths-part-1-46e02ab4a3ed)


### Prompt-Layered Architecture (PLA)

Academic framework (IJSRM 2025) that defines four layers: Prompt Composition,
Orchestration, Response Interpretation, Domain Memory. The Composition Layer
stores parameterized prompt templates as individual modules with metadata
(version, owner, task_type) and supports variable injection.

**What we take:** the separation between composition (assembling blocks into a
prompt) and orchestration (deciding which prompt to use, with what parameters).
xprompt handles composition only. The pipeline code (services, flows)
handles orchestration.

**What we skip:** the full four-layer stack. Over-engineered for most projects.

Source: [Prompt-Layered Architecture (PDF)](https://ijsrm.net/index.php/ijsrm/article/view/5670/3951)


### Banks -- Jinja2 macros and includes

Banks supports Jinja2 `{% macro %}` and `{% include %}` natively. Prompts can
define reusable macros (functions) and include other template files. No special
composition API -- it's all standard Jinja2.

**What we take:** the same approach. Jinja2 includes are the composition
mechanism. No custom syntax, no custom resolution beyond the loader.

Source: [Banks - GitHub](https://github.com/masci/banks)


### Semantic Kernel -- Prompty format

Microsoft's Prompty (`.prompty` files) bundles system message, few-shot
examples, and output instructions into a single YAML+Markdown file. Composition
across files is not supported -- each `.prompty` is self-contained.

**What we take:** the front-matter + Markdown body format. Our `.md` files use
the same structure.

**What we skip:** the single-file constraint. Our prompts can include blocks
from other files, which is the whole point of composition.

Source: [Semantic Kernel Prompty](https://www.developerscantina.com/p/semantic-kernel-prompty/)


### PromptLayer -- prompts as code

PromptLayer treats prompts as versionable, deployable, measurable code artifacts.
Core concepts from their Prompt Registry:

- **Centralized registry.** All prompts live in one place. Every LLM call
  fetches the prompt at runtime from the registry via SDK.
- **Release labels.** Each prompt has named labels (`prod`, `staging`, `dev`)
  pointing to specific versions. Deploying a new prompt = moving the `prod`
  label to a different version. No code change, no redeploy.
- **Version history with commit messages.** Every edit creates a numbered
  version with an optional commit message and metadata. Full audit trail.
- **Jinja2 and f-string templates.** Variables are injected at render time.
- **Analytics per version.** Each request is tagged with the prompt version
  used. You can compare quality metrics across versions directly.

**What we take:**

- **Release labels ~ our config overrides.** Their `prod`/`staging` labels
  solve the same problem as our config `prompts:` section: selecting
  which version is active without changing template files.
- **Version history ~ git history.** Their numbered versions with commit
  messages map directly to git commits on our `.md` files.
- **Prompts-as-code philosophy.** Prompts deserve the same rigor as application
  code -- versioning, review, rollback, measurement.

**What we skip:**

- **Hosted service.** PromptLayer is a SaaS platform. We need offline,
  git-native, zero-dependency prompt management.
- **Runtime retrieval.** They fetch prompts over HTTP at runtime. We load
  from the filesystem at startup. No network dependency.
- **Analytics integration.** Their per-version metrics are powerful but
  require their platform.

Source: [PromptLayer Prompt Registry](https://docs.promptlayer.com/features/prompt-registry),
[PromptLayer Quickstart](https://docs.promptlayer.com/quickstart)


### Summary: where xprompt sits

| System | Composition mechanism | Granularity | Version-aware includes |
|--------|----------------------|-------------|----------------------|
| Langfuse | Custom `@@@` tags, server-resolved | Prompt-level | Yes (version or label) |
| PromptLayer | None (single templates, no cross-prompt includes) | Prompt-level | N/A (labels select version, not composition) |
| Modular Prompt Design | Manual copy-paste between modules | Module-level | No |
| PLA | Parameterized templates in composition layer | Layer-level | Metadata only |
| Banks | Jinja2 `{% include %}` / `{% macro %}` | File-level | No (manual path) |
| Semantic Kernel / Prompty | None (single file) | N/A | N/A |
| **xprompt** | **Jinja2 `{% include %}` with custom loader** | **Block-level** | **Yes (config-driven)** |

The distinguishing feature: the custom Jinja2 loader makes `{% include %}`
version-aware. When you include a block, the loader checks the config override
map before resolving the file. A single config line can swap a block variant
across every prompt that uses it -- without modifying any template file.


## Alternative: Prompt-as-Code (prompt = Python class)

Everything above treats prompts as **data** -- Markdown files loaded by a
registry. There is a fundamentally different approach: make each prompt a
**Python object** (class or callable). The template is still Jinja2/Markdown,
but identity, metadata, composition, and versioning become native Python
concepts. You stop reinventing machinery that the language already provides.


### What it looks like

```python
from xprompt import Prompt

class ScoringRubric(Prompt):
    """Five-level scoring rubric."""
    is_block = True
    model = "sonnet"
    template_file = "scoring_rubric.md"

class EvalFramework(Prompt):
    """Analytical evaluation lenses."""
    is_block = True
    template_file = "eval_framework.md"

class Evaluate(Prompt):
    """Full document evaluation."""
    model = "opus"
    blocks = [ScoringRubric, EvalFramework]
    template_file = "evaluate.md"

    def render(self, **kwargs):
        # custom pre-processing, validation, whatever
        return super().render(**kwargs)
```

Caller:
```python
prompt = Evaluate()
text = prompt.render(document_name="API Spec", review_data=data)
meta = prompt.meta()  # {"model": "opus", "description": "Full document..."}
```


### What you get for free

| Feature | File-based (current design) | Prompt-as-code |
|---------|---------------------------|----------------|
| **Metadata** | YAML front-matter, parsed at load | Class attributes. Typed. IDE autocomplete. |
| **Composition** | Jinja2 `{% include %}` + custom loader | Class references. Python resolves dependencies. |
| **Versioning** | `default.md` + config override | Subclass or factory. Import the variant you want. |
| **Decorators** | N/A | `@cached`, `@validate_output`, `@log_render` -- arbitrary cross-cutting behavior |
| **Inheritance** | N/A | `class EvaluateV2(Evaluate): template_file = "..."` -- override one thing, inherit the rest |
| **Conditional composition** | Jinja2 `{% if %}` | Python `if/else` in `render()` or dynamic `blocks` list |
| **Type safety** | None (runtime errors on missing variables) | Type-check render args, IDE catches typos |
| **Introspection** | Scan filesystem, parse front-matter | `Prompt.__subclasses__()`, `inspect`, registry auto-discovers |
| **Testing** | Load file, render, assert string | Import class, call method, assert. Standard pytest. |
| **Reuse** | Copy file or include | Import and subclass. Python's native reuse mechanism. |


### Versioning with classes

Multiple approaches, all native Python:

**1. Subclass = variant:**
```python
class EvaluateCoT(Evaluate):
    """Variant: adds chain-of-thought reasoning."""
    template_file = "evaluate_cot.md"
    # inherits model, blocks, render logic
```

**2. Config selects class (same as current config override concept):**
```yaml
# config.yml
prompts:
  evaluator.evaluate: EvaluateCoT
```

Registry resolves `"evaluator.evaluate"` to the class, not a file.

**3. Factory pattern:**
```python
def get_evaluate_prompt(variant: str = "default") -> Evaluate:
    variants = {"default": Evaluate, "cot": EvaluateCoT}
    return variants[variant]()
```


### Composition with classes

Blocks are just prompts. Composition is object references.

```python
class Evaluate(Prompt):
    blocks = [ScoringRubric, EvalFramework, EvidenceGrounding]

    # Dynamic composition: override blocks per document type
    @classmethod
    def for_doc_type(cls, doc_type: str):
        extra = TypeBlocks.get(doc_type, [])
        instance = cls()
        instance.blocks = cls.blocks + extra
        return instance
```

No Jinja2 loader tricks. No custom resolution. Just Python.


### Decorators -- the exotic mechanics

This is where file-based approaches simply cannot compete.

```python
@cached(ttl=3600)          # render once, reuse for 1h
@log_render(logger)        # log every render with args + timing
@validate_schema("json")   # assert output matches JSON schema
class Evaluate(Prompt):
    ...
```

```python
# Cross-cutting concern: inject standard constraints into all prompts
def with_constraints(*constraint_blocks):
    def decorator(cls):
        cls.blocks = list(cls.blocks) + list(constraint_blocks)
        return cls
    return decorator

@with_constraints(EvidenceGrounding, NoInventedEvidence)
class Evaluate(Prompt):
    ...
```

These are impossible with Markdown files. You'd need to build each feature
from scratch in the registry. With classes, it's 3-line decorators.


### Tradeoffs

| | File-based | Prompt-as-code |
|-|-----------|----------------|
| **Prompt authors** | Edit Markdown. Zero Python needed. | Must write/read Python. Higher barrier. |
| **Separation from code** | Complete. Prompts are data files. | Prompts live in Python modules alongside code. |
| **Git diffs** | Clean Markdown diffs. | Python diffs. Still readable, but mixed with code. |
| **Non-developer access** | Anyone can edit `.md` files. | Requires Python familiarity. |
| **Power ceiling** | Limited by Jinja2 + custom loader. | Unlimited. Full language. |
| **Complexity** | Simple registry (~100 lines). | Base class + registry + decorators (~150-200 lines). |
| **Template visibility** | Open the `.md` file, see the prompt. | Open the `.py` file, find the `template` attribute. |


### Hybrid: classes with external templates

You can have both. The class provides identity, metadata, composition, and
behavior. The template body is still a `.md` file loaded from disk.

```python
class Evaluate(Prompt):
    model = "opus"
    template_file = "evaluate.md"
    blocks = [ScoringRubric, EvalFramework]

    @validate_schema("json")
    def render(self, **kwargs):
        return super().render(**kwargs)
```

This preserves:
- Clean Markdown diffs for template changes
- Non-developer-editable templates
- Class-based metadata, composition, and decorators
- Python-native versioning (subclass overrides `template_file`)


### Recommendation

The hybrid approach is the sweet spot:

- **Templates stay as `.md` files.** The prompt text is the thing that changes
  most often and benefits most from clean Markdown diffs. Keep it as data.
- **Classes provide the wiring.** Metadata, composition order, version
  selection, pre/post processing, validation. These are code concerns.
- **Decorators for cross-cutting.** Caching, logging, schema validation,
  constraint injection. Add them when needed, not speculatively.
- **Subclasses for variants.** `EvaluateCoT(Evaluate)` overrides
  `template_file` and inherits everything else. Cleaner than config-driven
  file switching.

This is ~150-200 lines for the base class + loader. Not heavier than the
file-only approach, but with a much higher ceiling.


## Open Questions

1. **Validation at load time.** Should the registry validate that all Jinja2
   variables in a template are documented in front-matter? Nice-to-have, not
   essential for v1.
2. **Block granularity.** How small is too small? A 3-line persona block is
   fine. A 1-line block that says "Do not invent evidence" is probably not worth
   its own file. Rule of thumb: a block earns its own file when it's either
   (a) reused across 2+ prompts, or (b) likely to be independently versioned.
