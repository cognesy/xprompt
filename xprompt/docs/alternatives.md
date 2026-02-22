# xprompt -- Alternatives Analysis

Landscape audit of Python libraries for LLM prompt management, measured
against our 7 requirements: prompts as classes, composition/nesting, Jinja2
templates, versioning/variants, registry/discovery, metadata, decorator support.


## Verdict

No existing library combines all 7 requirements. The space is fragmented:

- **Composition** libraries ignore versioning and registry
- **Versioning/registry** tools ignore class-based composition
- **Decorator-first** tools treat prompts as functions, not composable classes
- **Template-first** tools treat prompts as Jinja text, not Python objects


## Tier 1: Closest Matches

### Banks

- **PyPI**: [banks](https://pypi.org/project/banks/) -- v2.4.1 (Feb 2026)
- **GitHub**: 122 stars, actively maintained
- Jinja2-based prompt language with `Prompt`/`AsyncPrompt` classes
- Template registries, metadata, versioning as first-class citizen
- `Prompt` is a wrapper class, not a subclassable prompt definition
- Composition via Jinja2 template inheritance, set blocks, macros
- No decorator extensibility

| Requirement | Banks |
|-------------|-------|
| Prompts as classes | Partial -- wrapper, not subclassable |
| Composition | Yes -- Jinja2 includes/macros |
| Jinja2 | Yes -- core design |
| Versioning | Yes -- first-class |
| Registry | Yes -- `DirectoryTemplateRegistry` |
| Metadata | Yes |
| Decorators | No |

**Gap:** Prompts are Jinja templates, not Python classes. No `body()` returning
composable trees. No decorator support.


### ell

- **PyPI**: [ell-ai](https://pypi.org/project/ell-ai/) -- v0.0.17 (Feb 2025)
- **GitHub**: 5,900 stars, active
- "Prompts as programs" -- decorated functions become Language Model Programs
- Automatic versioning via code analysis, Ell Studio for visualization
- Composition via function calls (LMPs call other LMPs)
- Function-based only (`@ell.simple`, `@ell.complex`)

| Requirement | ell |
|-------------|-----|
| Prompts as classes | No -- function-based |
| Composition | Yes -- function calls |
| Jinja2 | No |
| Versioning | Yes -- automatic |
| Registry | Partial -- local store |
| Metadata | No |
| Decorators | Yes -- core design |

**Gap:** Functions, not classes. No template files. No config-driven variants.
Best versioning story in the space.


### Mirascope

- **PyPI**: [mirascope](https://pypi.org/project/mirascope/) -- v2.2.2 (Feb 2026)
- **GitHub**: 1,400 stars, very active
- `BasePrompt` subclasses with fields, `@prompt_template` decorator
- Multi-provider support, structured outputs via Pydantic
- No tree/block composition model

| Requirement | Mirascope |
|-------------|-----------|
| Prompts as classes | Yes -- `BasePrompt` |
| Composition | Limited -- prompts call prompts via `run()` |
| Jinja2 | No -- custom template syntax |
| Versioning | Partial -- CLI-based |
| Registry | No |
| Metadata | No |
| Decorators | Yes -- `@prompt_template`, `@llm.call` |

**Gap:** No composable tree model. No Jinja2. No config-driven variants.
Strongest class-based model among active libraries.


### prompt-components

- **GitHub**: [jamesaud/prompt-components](https://github.com/jamesaud/prompt-components) -- 4 stars
- Dataclass-based prompt components with `render()`, recursive composition
- Jinja2 support, lifecycle hooks (`_pre_render`, `_post_render`)
- Swappable components via `@dataclass_swappable_component`

| Requirement | prompt-components |
|-------------|-------------------|
| Prompts as classes | Yes -- dataclass components |
| Composition | Yes -- recursive render |
| Jinja2 | Yes |
| Versioning | No |
| Registry | No |
| Metadata | No |
| Decorators | Yes |

**Gap:** No versioning, no registry, no config-driven variants. 4-star hobby
project, 25 commits. Closest to our `body()` + composable tree pattern.


## Tier 2: Partial Matches

### Microsoft Prompty

- **GitHub**: 1,200 stars, beta
- `.prompty` file format: YAML frontmatter + Jinja2 body
- No Python classes, no composition across files
- Closest to our "template files with frontmatter" idea

### LangChain Prompts

- `PromptTemplate`, `ChatPromptTemplate`, `PipelinePromptTemplate`
- Composition via pipeline and `+` operator
- Template containers, not subclassable definitions
- No versioning, no registry

### Haystack PromptBuilder

- Jinja2-based `PromptBuilder` component for pipeline composition
- Builder pattern, not class-based
- No versioning, no registry

### Instructor (Jinja2 templating)

- Added Jinja2 context-based rendering to `create()` calls
- Focused on output validation, not prompt authoring
- No classes, no composition, no versioning

### promptic

- **GitHub**: 272 stars
- Decorator-based: docstrings become prompts (`@llm`)
- Minimal, function-based, no composition or versioning


## Tier 3: Token-Budgeting / Composition-Only

### PriomptiPy

- **GitHub**: 115 stars
- Functional components with `Scope`, `Isolate` for token budgeting
- React-inspired composition model
- No versioning, no registry, no template files

### py-priompt

- **GitHub**: 65 stars
- React/FastHTML-inspired functional components
- Focus on priority-based token allocation
- No versioning, no registry


## Tier 4: Hosted Platforms (SDKs, not libraries)

These manage prompts in a server, not as code in your repo:

| Platform | Versioning | Registry | A/B Variants | Open Source |
|----------|------------|----------|--------------|-------------|
| Langfuse | Yes (labels) | Yes | Yes | Yes (self-host) |
| PromptLayer | Yes (numbered) | Yes | Yes (traffic split) | No |
| MLflow Prompt Registry | Yes (aliases) | Yes | Yes | Yes |
| Braintrust | Yes | Yes | Yes | No |
| Humanloop | Yes | Yes | Yes | No |

Server-side prompt management. Strong versioning and A/B. Requires
infrastructure. Not code-first.


## Gap Analysis

| Requirement | Our Design | Best Existing |
|-------------|-----------|---------------|
| Classes with `body()` tree | Core design | prompt-components (4 stars, hobby) |
| Composable block nesting | `_flatten()`, 15 lines | prompt-components, PriomptiPy |
| Jinja2 template files | `.md` with frontmatter | Banks, Prompty |
| Config-driven variants | `config.yml` prompts section | Langfuse/PromptLayer (hosted only) |
| Registry/discovery | `PromptRegistry` | Banks (`DirectoryTemplateRegistry`) |
| Metadata per prompt | Frontmatter + class attrs | Banks, Prompty |
| Decorator support | Standard Python | ell, Mirascope, promptic |

No library covers more than 4 of 7. The combination of class-based identity
+ composable trees + template files + config-driven variants is unique.


## What to study from each

| Library | Take |
|---------|------|
| Banks | Registry patterns, metadata conventions, template loading |
| ell | Automatic versioning via code analysis, studio visualization |
| Mirascope | `BasePrompt` class design, Pydantic integration |
| prompt-components | Recursive render pattern, swappable component decorator |
| Prompty | Frontmatter schema conventions |


## Sources

- [Banks](https://github.com/masci/banks) -- PyPI, GitHub
- [ell](https://github.com/MadcowD/ell) -- PyPI, GitHub
- [Mirascope](https://github.com/Mirascope/mirascope) -- PyPI, GitHub
- [prompt-components](https://github.com/jamesaud/prompt-components) -- GitHub
- [Prompty](https://github.com/microsoft/prompty) -- GitHub
- [PriomptiPy](https://github.com/tg1482/priomptipy) -- GitHub
- [py-priompt](https://github.com/zenbase-ai/py-priompt) -- GitHub
- [promptic](https://github.com/knowsuchagency/promptic) -- GitHub
- [LangChain Prompt Composition](https://python.langchain.com/v0.2/docs/how_to/prompts_composition/)
- [Haystack PromptBuilder](https://docs.haystack.deepset.ai/docs/promptbuilder)
- [Instructor Templating](https://python.useinstructor.com/concepts/templating/)
- [Langfuse Prompt Management](https://langfuse.com/docs/prompt-management/get-started)
- [PromptLayer Registry](https://docs.promptlayer.com/features/prompt-registry/overview)
- [MLflow Prompt Registry](https://mlflow.org/docs/latest/genai/prompt-registry/)
