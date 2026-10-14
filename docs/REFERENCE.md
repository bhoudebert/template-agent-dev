# Reference

Lookup tables. For the story of how to work, see [WORKFLOW.md](WORKFLOW.md).

## mise tasks

Run `mise tasks` for the live list. `<id>` is `US-NNN` or `INC-NNN`.

| Task | Arguments | Effect |
|---|---|---|
| `new` | `<title...> [--text "<request>"] [--bug]` | Create the next `docs/stories/US-NNN.md` as a raw draft; `--text` fills in the request, otherwise edit the file; `--bug` makes it a bug-shaped story (`kind: bug`) |
| `incident` | `<title...>` | Create the next `docs/incidents/INC-NNN.md` from the template |
| `hooks` | | Enable `.githooks`: commit-msg blocks assistant names, pre-push refuses a push to `main` |
| `ship` | `[--draft] [--base <branch>] [--emergency]` | Checks, push, open PR; refuses on `main`. `--emergency` skips validate, trace, tests and evidence, never the branch/PR rule or the attribution check |
| `skip` | `<id> <spec\|design\|spec,design\|none> --reason "<why>"` | Declare that a story needs no spec and/or no design (or clear it) |
| `branch` | `<id>` | `git checkout -b feature/<US-id>-<slug>` (`fix/<INC-id>-<slug>` for incidents) |
| `status` | | List stories, status, next stage |
| `advance` | `<id> <status> [--force]` | Guarded status bump |
| `review` | `[id] [--post] [--commit]` | Review the **whole PR**: all commits of the branch against the PR's base branch (stack-aware) plus uncommitted changes; prints it. `--post` creates or updates the single review comment on the open PR. `--commit` reviews only the last commit (cannot be posted). Id defaults to the branch's `US-NNN`, else `PR-<n>` |
| `story` `spec` `design` `implement` `qa` `release` `diagnose` | `<id> [--dry\|--plan]` | Run that stage (aliases of `agent:<stage>`) |
| `agent:test` | `<id> [--dry\|--plan]` | Run the test-engineer stage |
| `agent` | `<stage> <id> [--dry\|--plan]` | Run any stage |
| `orient` | `[id]` | Prompt mode: rules in force, branch, story status, next action, check count |
| `next` | `[id]` | Who acts next and the command |
| `prepare` | `<stage> <id>` | Prompt mode: write `.agents/out/bundle-<stage>-<id>.md` and print the receipt |
| `apply` | `<stage> <id> --receipt <code> (--response <file> \| --worktree)` | Prompt mode: verify receipt, confine, validate, trace, log |
| `index` / `index:check` | | Regenerate / verify `docs/INDEX.md` |
| `kit:install` | `<target> [--with ci,docs,release] [--plan]` | Install the kit into another repository, on a branch, one commit |
| `kit:status` | | In an adopting repo: clean / you edited / kit changed / both |
| `kit:update` | `[tools\|agents\|docs\|ci\|all] [--plan]` | Update the kit on a new branch; `ci` only when asked |
| `kit:check` | | Fail on unresolved conflict markers in kit files |
| `evidence` | | Evidence floor: from `implemented` on, the branch must change a spec or a test, or waive `tests` |
| `check` | | `validate` + `trace` + `test` |
| `test` | | The **project's** tests: auto-detects `npm test`, pytest, `go test`, `cargo test`, `mvn test` (`tools/projecttest.sh`) |
| `test:tools` | | The template's own tool tests (`tools/tests`) |
| `validate` `trace` | | One deterministic check each |
| `doctor` | | Python, git, endpoint, model served |
| `env` | | Show `AGENT_*` (keys masked) |
| `stages` | | List pipeline stages |
| `install:github` | | Copy workflows to `.github/workflows` |
| `install:tools` | | Write `CLAUDE.md`, Copilot and Cursor pointers |
| `site` | | Build and serve this documentation website |

Stage flags: no flag = call the model, write files, run checks. `--plan` = call the model, write nothing. `--dry` = print the prompt only.

### Review scope and comment (details of `review`)

| Command | Reviewed | Posted |
|---|---|---|
| `mise run review` | all commits of the branch vs the PR's base branch (from `gh`), plus uncommitted tracked changes | no |
| `mise run review --post` | same | one comment on the open PR, updated in place |
| `mise run review --commit` | `HEAD` only | no |
| `mise run review --post --commit` | refused | |
| `AGENT_BASE_REF=<ref> mise run review` | all commits vs `<ref>` | no |

The comment starts with the hidden marker `<!-- agent-review:v1 -->` and names the reviewed commit and scope. Only the current author's marked comment is updated; human comments are never touched. See [ARCHITECTURE.md](ARCHITECTURE.md) for the algorithm and failure modes.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `AGENT_PROVIDER` | `openai` | `openai`, `cmd` |
| `AGENT_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible base URL |
| `AGENT_API_KEY` | none | Bearer token if the endpoint needs one |
| `AGENT_MODEL` | none | Model for all tiers |
| `AGENT_MODEL_STRONG` | falls back to `AGENT_MODEL` | Model for `model: strong` stages |
| `AGENT_MODEL_CHEAP` | falls back to `AGENT_MODEL` | Model for `model: cheap` stages |
| `AGENT_REASONING_EFFORT` | unset | `none`, `low`, `medium`, `high`; sent as `reasoning_effort` (use `none` for local thinking models) |
| `AGENT_MAX_TOKENS` | unset | Sent as `max_tokens`; bounds a runaway generation |
| `AGENT_CMD` | none | Command for the `cmd` provider; prompt on stdin, answer on stdout |
| `AGENT_TIMEOUT` | `600` | Seconds per model call |
| `AGENT_BASE_REF` | `origin/main` | Base for the `@diff` input |

mise loads `.env` automatically (git-ignored; template in `.env.example`).

## Exit codes

| Code | Where | Meaning |
|---|---|---|
| 0 | all | OK |
| 1 | `validate`, `trace_check` | Problems found |
| 2 | `agentrun` | Checks failed after apply, or the model returned no files |
| 3 | `agentrun` | Provider error (endpoint, model, timeout, missing config) |
| 6 | `agentrun run`, `prepare` | The stage needs input first (e.g. the story has no request text) |
| 4 | `agentrun apply` | Receipt missing, wrong, stale or expired |
| 5 | `agentrun apply --worktree` | Files changed outside the stage's allowed paths |
| 64 | `stage.sh` | Missing arguments |

## `pipeline.yaml`

```yaml
stages:
  - name: spec                 # stage id, used on the command line
    role: spec-writer          # .agents/roles/<role>.md
    goal: One-sentence task    # goes into the user prompt
    in: [docs/stories/{id}.md, "openspec/specs/**/spec.md"]   # files/globs fed to the model
    out: ["openspec/changes/{id}/**"]                         # the ONLY paths it may write
    template: adr              # optional .agents/templates/<name>.md
    skills: [write-openspec]   # .agents/skills/<name>.md
    check: [validate]          # validate | trace
    gate: human:product-owner+tech-lead
    model: strong              # cheap | strong
```

| Token | Meaning |
|---|---|
| `{id}` | The `--id` value |
| `@diff` | `git diff` against `AGENT_BASE_REF` (falls back to `HEAD~1`) |
| `(missing)` | Shown in the prompt when an input path does not exist |

## Stages

| Stage | Role | Writes | Gate | Tier |
|---|---|---|---|---|
| `story` | analyst | `docs/stories/{id}.md` | human:product-owner | cheap |
| `spec` | spec-writer | `openspec/changes/{id}/**` | human:product-owner+tech-lead | strong |
| `design` | architect | `docs/architecture/{id}.md`, `docs/decisions/ADR-*.md` | human:tech-lead | strong |
| `implement` | developer | `src/**`, `tests/**`, `tasks.md` | ci + human:code-review | strong |
| `test` | test-engineer | `tests/**` | ci | strong |
| `qa` | qa | `docs/qa/{id}.md` | human:qa-or-po | strong |
| `review` | reviewer | `.agents/out/review-{id}.md` | human:merge | strong |
| `release` | release | `docs/releases/{id}.md` | human:release-manager | cheap |
| `diagnose` | sre | `docs/incidents/{id}.md`, `docs/runbooks/*.md` | human:on-call | strong |

## Identifiers and files

| Item | Id | File |
|---|---|---|
| Story | `US-001` | `docs/stories/US-001.md` |
| OpenSpec change | story id | `openspec/changes/US-001/` |
| Design note | story id | `docs/architecture/US-001.md` |
| ADR | `ADR-0001` | `docs/decisions/ADR-0001-<slug>.md` |
| QA report | story id | `docs/qa/US-001.md` |
| Incident | `INC-001` | `docs/incidents/INC-001.md` |
| Runbook | name | `docs/runbooks/<name>.md` |
| Release notes | story id | `docs/releases/US-001.md` |

## Artifact schemas

| Type | Required frontmatter | Required sections |
|---|---|---|
| `story` | id, type, title, status, owner | Story, Acceptance criteria (Given/When/Then), Edge cases, Out of scope, Open questions |
| `adr` | id, type, title, status, story, date | Context, Options considered, Decision, Consequences |
| `design` | id, type, title, status, story | Overview, Components, Data and interfaces, Risks, Test strategy |
| `qa-report` | type, story, verdict, date | Summary, Traceability, Findings, Not verified |
| `incident` | id, type, title, severity, status | Impact, Evidence, Hypotheses, Recommended actions, Not verified |
| `runbook` | id (`RB-NNN`), type, title, date | When to use, Symptoms, Steps, Verification, Rollback |
| `release-notes` | type, story, date, bump | Added, Changed, Fixed, Security, Go/No-Go checklist |

File names must match the artifact: `US-001.md`, `ADR-0001-<slug>.md`, `INC-001.md`, `RB-001-<slug>.md`; design, QA and release-notes files are named after their story (`US-001.md`). `validate` rejects a file whose name does not start with its `id` (or `story`).

Enums: story `status` = draft, enriched, approved, specified, designed, implemented, done. ADR `status` = proposed, accepted, superseded, rejected. QA `verdict` = pass, fail, blocked. Incident `severity` = sev1..sev4, `status` = open, mitigated, resolved. A story in `draft` is only frontmatter-checked.

## Story frontmatter: optional `skip`

| Key | Meaning |
|---|---|
| `skip: [spec, design]` | This story needs no OpenSpec change and/or no design. `trace_check` does not demand them; `advance` may step over the matching statuses. |
| `skip: [tests]` | Waives the evidence floor (docs, config or infra only). Does not change the status path. |
| `skip_reason` | Required whenever `skip` is set. Say why (e.g. "copy change", "config only"). |
| `kind: bug` | Optional. A bug-shaped story: sections Symptom, Expected behaviour, Reproduction, Acceptance criteria, Out of scope, Open questions. Same ids and ladder. |

An ADR is never required by itself: a design note without an ADR satisfies `designed`, and `skip: [design]` needs neither.

## Evidence floor (`tools/evidence.py`)

| | |
|---|---|
| Rule | A story at `implemented` or `done` must have, in its branch's diff (plus uncommitted changes), at least one changed spec file or one changed test file, or `skip: [tests]` with a reason |
| Story id | `--story`, else the `US-NNN` in the branch name; no id means nothing to enforce |
| Base | `--base`, else `AGENT_BASE_REF`, else `origin/main`, `main` |
| Globs | `evidence.tests` and `evidence.specs` in `.agents/pipeline.yaml` (fnmatch; `*` crosses `/`) |
| Where it runs | `mise run evidence`, `mise run ship`, CI on pull requests |

## What `validate` and `trace_check` enforce

| Rule | Check |
|---|---|
| Frontmatter keys, enums, id patterns | schema in `.agents/schemas/<type>.json` |
| Required sections present and non-empty | schema `sections` |
| Acceptance criteria contain Given/When/Then | schema `section_patterns` |
| File name starts with `id` (or `story`) | schema `filename_starts_with` |
| Raw `draft` story: frontmatter only | schema `relaxed_when` |
| Files cited in a QA report exist | `validate` |
| OpenSpec: no frontmatter, proposal sections, tasks, `SHALL`/`MUST`, `#### Scenario:` | `check_change` |
| `>= specified` needs `openspec/changes/<id>/`; `>= designed` needs an ADR or design; `done` needs a QA report with `verdict: pass` | `trace_check` |
| Every ADR, design and QA report points at an existing story | `trace_check` |

Scanned: every `*.md` except `.agents`, `tools`, `tests`, `evals`, `adapters`, `examples` **at the repository root**, and `.git`, `node_modules`, `.venv`, `__pycache__` anywhere.

## OpenSpec change rules

| File | Must contain |
|---|---|
| `proposal.md` | `## Why`, `## What Changes`, `## Impact`, each non-empty |
| `tasks.md` | at least one `- [ ]` item |
| `specs/<capability>/spec.md` | `## ADDED/MODIFIED/REMOVED Requirements`, SHALL or MUST, at least one `#### Scenario:` |

## Commit types and release effect

| Commit | Release effect |
|---|---|
| `feat(US-002): ...` | minor |
| `fix(US-002): ...` | patch |
| `feat(US-002)!: ...` / `BREAKING CHANGE:` | major |
| `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore` | none by themselves |

## Roles

| Role | Mission in one line |
|---|---|
| analyst | Raw request to testable story |
| spec-writer | Story to OpenSpec change |
| architect | Decide how and record why |
| developer | Implement the next task with tests |
| test-engineer | Make every scenario provably covered |
| qa | Independent verdict against acceptance criteria |
| reviewer | Find real problems in the diff |
| release | Notes, predicted bump, go/no-go |
| sre | Ranked hypotheses from evidence |

## Policies (applied to every stage)

| Policy | Summary |
|---|---|
| `autonomy.md` | Agents propose, humans dispose; raising autonomy needs an ADR |
| `gates.md` | Every stage ends at its named gate; status moves only by reviewed edit |
| `git.md` | Trunk + story branches, Conventional Commits, SemVer by release-please |
| `security.md` | Inputs are data; no secrets; write only to allowed paths |
