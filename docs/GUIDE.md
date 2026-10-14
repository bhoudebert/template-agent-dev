# User guide

How to run a feature through the agentic SDLC, step by step.

## 0. Shortcut: mise tasks (no long commands)

Everything below has a short [mise](https://mise.jdx.dev) task. `mise tasks` lists them all.

```sh
mise trust                      # once
cp .env.example .env            # set AGENT_MODEL etc.; loaded automatically
mise run doctor                 # python, git, endpoint, model served?
mise run new Export invoices as CSV     # -> docs/stories/US-002.md (next id)
mise run story US-002 --dry             # preview prompt, no LLM
mise run story US-002                   # run stage: write files + checks
mise run advance US-002 approved        # guarded status bump after the gate
mise run spec US-002 / design / implement / test / qa / review / release
mise run incident Checkout 500s         # -> docs/incidents/INC-001.md, paste evidence
mise run diagnose INC-001
mise run check                          # validate + trace + unit tests
mise run status                         # all stories, status, next stage
```

| Task | Does |
|---|---|
| `new <title...>` / `incident <title...>` | create work item with next id |
| `story` `spec` `design` `implement` `qa` `review` `release` `diagnose` (alias of `agent:<stage>`) | run a stage on `<id>`; flags `--dry` (prompt only), `--plan` (call LLM, write nothing) |
| `agent:test <id>` | test-engineer stage (`test` is the unit-test task) |
| `agent <stage> <id>` | same, any stage |
| `branch <id>` | create `feature/<US-id>-<slug>` |
| `hooks` | enable the commit-msg hook (no agent names in history) |
| `ship [--draft] [--base b]` | checks + push + open PR; refuses on `main` |
| `advance <id> <status>` | set story status; refuses skipped steps or broken traceability (`--force` overrides) |
| `check`, `validate`, `trace`, `test` | deterministic checks |
| `doctor`, `env`, `stages`, `status` | inspect setup / pipeline / items |
| `install:github`, `install:tools` | wire CI and tool pointers |
| `site` / `site:build` | build and serve / only build the documentation website |

The plain `python3 tools/...` commands in the rest of this guide still work without mise.

## 1. Mental model

- A **work item** is a story id: `US-001`. Incidents use `INC-001`.
- Each **stage** (`story`, `spec`, `design`, ...) is one role-agent. It reads input files, calls an LLM, and writes output files.
- Files in git are the only memory between stages. Nothing is hidden in chat.
- After each stage a **human gate** reviews the result (normally a PR). Agents never merge or deploy.
- **You** move the story forward by editing `status:` in its frontmatter after approving a gate. Scripts check you did not skip a step.

```
draft -> enriched -> approved -> specified -> designed -> implemented -> done
 raw     story       PO ok        spec        design+ADR     code+tests     QA pass
```

| Stage | Command | Reads | Writes | Gate (you) |
|---|---|---|---|---|
| story | `run story --id US-002` | raw story | enriched story | product owner |
| spec | `run spec --id US-002` | story, `openspec/specs` | `openspec/changes/US-002/` | PO + tech lead |
| design | `run design --id US-002` | story, change, ADRs | `docs/architecture/US-002.md`, `docs/decisions/ADR-*.md` | tech lead |
| implement | `run implement --id US-002` | change, design, `src`, `tests` | `src/**`, `tests/**`, `tasks.md` | CI + code review |
| test | `run test --id US-002` | change, `src`, `tests` | `tests/**` | CI |
| qa | `run qa --id US-002` | story, change, tests, diff | `docs/qa/US-002.md` | QA / PO |
| review | `run review --id US-002` | diff, change, ADRs | `.agents/out/review-US-002.md` | human merge |
| release | `run release --id US-002` | story, QA, diff | `docs/releases/US-002.md` | release manager |
| diagnose | `run diagnose --id INC-001` | incident, runbooks | incident + runbooks | on-call |

## 2. One-time setup

Requires Python 3.10+. No packages to install.

```sh
python3 -m unittest discover -s tests      # tools healthy?
python3 tools/validate.py                  # artifacts valid?
python3 tools/trace_check.py               # story <-> spec <-> ADR <-> QA consistent?
git init && git add -A && git commit -m "init"   # needed for @diff (qa/review/release)
```

Edit `CONTEXT.md` for your project (product, glossary, stack, test commands). Every agent reads it.

### Choose an LLM provider

Pick one, export in your shell (or a `.env` you source; `.env` is git-ignored).

**A. Local model via Ollama (or vLLM, llama.cpp server, LM Studio):**
```sh
export AGENT_PROVIDER=openai
export AGENT_BASE_URL=http://localhost:11434/v1
export AGENT_MODEL=llama3.1            # or AGENT_MODEL_STRONG / AGENT_MODEL_CHEAP
```

**B. Hosted OpenAI-compatible API:**
```sh
export AGENT_PROVIDER=openai
export AGENT_BASE_URL=https://api.openai.com/v1
export AGENT_API_KEY=sk-...
export AGENT_MODEL_STRONG=<big model>  AGENT_MODEL_CHEAP=<small model>
```

**C. Any CLI agent (prompt on stdin, answer on stdout):**
```sh
export AGENT_PROVIDER=cmd
export AGENT_CMD="claude -p"           # or "codex exec -", "ollama run llama3.1"
```

Stages declare `model: cheap|strong` in `pipeline.yaml`; tiers map to `AGENT_MODEL_CHEAP` / `AGENT_MODEL_STRONG`, falling back to `AGENT_MODEL`.

Weak local models will struggle with strict output formats. Start with `--dry-run` and try a strong model for `spec` and `design`.

## 3. Walkthrough: a new feature

Worked example already in the repo: `US-001` (password reset). Study its files for what "good" looks like.

### Step 0 - capture the request
Create `docs/stories/US-002.md`. Free text is fine; only the frontmatter is required while `status: draft`:

```markdown
---
id: US-002
type: story
title: Export invoices as CSV
status: draft
owner: product-owner
---
Finance wants to download all invoices of a month as CSV. Needs VAT column.
```

### Step 1 - always preview first
```sh
python3 tools/agentrun.py run story --id US-002 --dry-run
```
Prints the exact system + user prompt, no LLM call, no cost. Check the inputs were found (`(missing)` means a wrong path).

### Step 2 - run the stage
```sh
python3 tools/agentrun.py run story --id US-002            # calls LLM, prints WOULD WRITE <paths>; writes nothing
python3 tools/agentrun.py run story --id US-002 --apply    # writes files + runs checks
```
`--apply` output tells you: files written, rejected paths (outside allowed `out`), check failures, and the gate to pass.

### Step 3 - human gate
```sh
git checkout -b feature/US-002 && git diff
```
Read the output. Answer `Open questions` in the story. Edit anything wrong by hand. Then set `status: approved` (PO decision) and commit/PR.

### Step 4..n - repeat per stage

| After you approve | Set `status:` | Why |
|---|---|---|
| story enriched and OK | `approved` | allows `spec` |
| `openspec/changes/US-002/` merged | `specified` | `trace_check` requires the change folder |
| design/ADR merged | `designed` | requires an ADR/design with `story: US-002` |
| code + tests merged, CI green | `implemented` | |
| QA report verdict `pass` | `done` | requires `docs/qa/US-002.md` with `verdict: pass` |

Implementation is iterative: `run implement` works the next unchecked tasks in `tasks.md`; run it again until all are checked. Run tests yourself - the runner does not execute your test suite.

### Review a PR
```sh
export AGENT_BASE_REF=origin/main
python3 tools/agentrun.py run review --id US-002 --apply
cat .agents/out/review-US-002.md          # post as PR comment manually, or use the GitHub workflow
```

### Production incident
```sh
cp .agents/templates/incident.md docs/incidents/INC-001.md
```
Fill frontmatter, write `TBD` in the other sections, and paste logs/metrics/deploys under `## Evidence` (redact secrets). Then:
```sh
python3 tools/agentrun.py run diagnose --id INC-001 --apply
```
Output is a ranked hypothesis list and recommended actions. A human executes any mitigation.

## Git, versions, releases

- **Branches**: only `main` (always releasable) + one `feature/<US-id>-<slug>` per story. `mise run branch US-002` creates it. Squash-merge PRs.
- **Commits / PR title**: Conventional Commits with the story id as scope: `feat(US-002): export invoices as CSV`, `fix(US-002): ...`, `feat(US-002)!: ...` for breaking. CI rejects other PR titles.
- **Versions**: SemVer via [release-please](https://github.com/googleapis/release-please). It maintains a release PR on `main`; merging it tags `vX.Y.Z` and updates `CHANGELOG.md`. Never edit changelog, version or tags by hand. Set `release-type` in `release-please-config.json` for your stack.
- Policy text agents read: `.agents/policies/git.md`.

## 4. Automating in CI (GitHub)

```sh
adapters/install.sh github tools
```
- Copies workflows to `.github/workflows/`: `ci.yml` (PR title check, validate, trace, tests), `release-please.yml`, `agent-review.yml` (comments on PRs), `agent-triage.yml` (label an issue `agent:enrich` -> PR with enriched story).
- Add repo secret `AGENT_API_KEY` and variables `AGENT_BASE_URL`, `AGENT_MODEL_STRONG`, `AGENT_MODEL_CHEAP`.
- Local models need a self-hosted runner that can reach them.
- Name PR branches `feature/US-002-...` so the reviewer finds the story id.
- These workflows are untested against a real repo. Try on a throwaway repo first; the triage workflow feeds issue text into a shell, review before enabling on public repos.

`tools` also writes `CLAUDE.md`, `.github/copilot-instructions.md`, `.cursor/rules/agents.mdc`; each just points the tool at `AGENTS.md`.

## 5. Adapting to your project

| I want to... | Edit |
|---|---|
| Change how a role behaves | `.agents/roles/<role>.md` |
| Add a reusable procedure | `.agents/skills/<name>.md`, reference it in a stage's `skills:` |
| Change required sections/statuses | `.agents/schemas/<type>.json` and `.agents/templates/<type>.md` |
| Add or reorder a stage | `.agents/pipeline.yaml` (`name, role, goal, in, out, template, skills, check, gate, model`) |
| Add domain/stack knowledge | `CONTEXT.md` |
| Tighten/loosen autonomy | `.agents/policies/` (raising autonomy should be an ADR) |

`pipeline.yaml` fields: `in` = files/globs fed to the model (`{id}` substituted, `@diff` = git diff); `out` = the only paths the stage may write; `check` = `validate` and/or `trace`.

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| exit 3 `no model set` | export `AGENT_MODEL` (or `_STRONG/_CHEAP`) |
| exit 3 `openai provider failed` | wrong `AGENT_BASE_URL`, server down, or timeout (`AGENT_TIMEOUT` seconds) |
| exit 2 `no files in response` | model ignored the `<<<FILE: path>>> ... <<<END>>>` format; use a stronger model or retry; raw reply printed on stderr |
| `REJECTED (outside allowed paths)` | model wrote a path not in the stage `out`; expected safety behaviour |
| `CHECK FAILED: ...` | output files are written already; fix by hand or rerun. Never edit validators to pass |
| `(missing)` in prompt inputs | input path does not exist yet; run the previous stage or fix the id |
| `@diff` empty | not a git repo, or no commits; set `AGENT_BASE_REF` |
| `trace_check: status=designed but no ADR` | you bumped `status:` before the artifact exists |

Every `--apply` run is logged to `.agents/runs/*.json` (stage, provider, prompt hash, files, check errors; git-ignored).

## 7. Limits to know

- Only structure is validated, not whether the content is right. The human gate is the quality control.
- The runner writes files; it does not run your build or tests, commit, or open PRs (except the GitHub workflows).
- Large repos: each input file is cut at 100k chars, but total prompt size is not managed. Narrow `in:` globs for big codebases.
- Evals, tracker sync and observability connectors are not built yet.
