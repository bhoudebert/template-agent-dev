# Reference

Lookup tables. For the story of how to work, see [WORKFLOW.md](WORKFLOW.md).

## mise tasks

Run `mise tasks` for the live list. `<id>` is `US-NNN` or `INC-NNN`.

| Task | Arguments | Effect |
|---|---|---|
| `new` | `<title...>` | Create the next `docs/stories/US-NNN.md` as a raw draft |
| `incident` | `<title...>` | Create the next `docs/incidents/INC-NNN.md` from the template |
| `hooks` | | Enable `.githooks` (commit-msg blocks agent names) |
| `ship` | `[--draft] [--base <branch>]` | Checks, push, open PR; refuses on `main` |
| `branch` | `<id>` | `git checkout -b feature/<US-id>-<slug>` (`fix/<INC-id>-<slug>` for incidents) |
| `status` | | List stories, status, next stage |
| `advance` | `<id> <status> [--force]` | Guarded status bump |
| `review` | `[id] [--post]` | Review the current branch's diff (plus uncommitted changes) and print it; `--post` creates or updates one review comment on the open PR (never a second one). Id defaults to the branch's `US-NNN`, else `PR-<n>` |
| `story` `spec` `design` `implement` `qa` `release` `diagnose` | `<id> [--dry\|--plan]` | Run that stage (aliases of `agent:<stage>`) |
| `agent:test` | `<id> [--dry\|--plan]` | Run the test-engineer stage |
| `agent` | `<stage> <id> [--dry\|--plan]` | Run any stage |
| `check` | | `validate` + `trace` + `test` |
| `validate` `trace` `test` | | One deterministic check each |
| `doctor` | | Python, git, endpoint, model served |
| `env` | | Show `AGENT_*` (keys masked) |
| `stages` | | List pipeline stages |
| `install:github` | | Copy workflows to `.github/workflows` |
| `install:tools` | | Write `CLAUDE.md`, Copilot and Cursor pointers |
| `site` | | Build and serve this documentation website |

Stage flags: no flag = call the model, write files, run checks. `--plan` = call the model, write nothing. `--dry` = print the prompt only.

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
