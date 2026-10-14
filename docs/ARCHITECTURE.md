# Architecture: how it works inside

## Design goals

- **Vendor-neutral**: works with a local model, a hosted API or any CLI agent. No feature of one product is required.
- **Files are the memory**: every stage reads and writes plain files in git. Nothing lives in a chat.
- **Humans decide**: agents propose, people approve at named gates.
- **Deterministic guard rails**: shape and traceability are checked by scripts, not by a model.
- **Zero dependencies**: stdlib Python only; copy the repo and it runs.

## Three layers

```
 CONTENT (portable md/yaml)   AGENTS.md  CONTEXT.md  .agents/{roles,skills,policies,templates,schemas,pipeline.yaml}
                              openspec/  docs/  src/  tests/
 CORE (stdlib python)         tools/agentrun.py  validate.py  trace_check.py  providers.py  items.py  doctor.py
 ADAPTERS (replaceable)       adapters/github/workflows   adapters/install.sh   mise.toml   tool pointers
```

Rule: content and core never use a vendor feature. Vendor specifics live only in adapters, so swapping CI host, assistant or model changes one thin layer.

## Repository map

| Path | Role |
|---|---|
| `AGENTS.md` | Universal entry point read by any coding agent |
| `CONTEXT.md` | Project facts: glossary, stack, conventions |
| `.agents/pipeline.yaml` | Declarative stage graph |
| `.agents/roles/*.md` | One system prompt per role |
| `.agents/skills/*.md` | Reusable procedures a stage can attach |
| `.agents/policies/*.md` | Always-on rules: autonomy, gates, git, security |
| `.agents/templates/*.md` | Skeleton of each artifact type |
| `.agents/schemas/*.json` | Machine-checkable shape of each artifact type |
| `.agents/runs/` | Audit log of runs (git-ignored) |
| `.agents/out/` | Ephemeral outputs such as the PR review (git-ignored) |
| `openspec/specs/`, `openspec/changes/<US-id>/` | Current behaviour; proposed deltas |
| `docs/stories`, `architecture`, `decisions`, `qa`, `incidents`, `runbooks`, `releases` | Work artifacts |
| `tools/` | Runner, validators, helpers |
| `adapters/` | CI workflows, tool pointers |

## What happens when you run a stage

`mise run spec US-002` expands to `python3 tools/agentrun.py run spec --id US-002 --apply`.

```
1. load .agents/pipeline.yaml, find stage "spec"
2. build SYSTEM prompt
     AGENTS.md
     CONTEXT.md
     .agents/roles/<role>.md
     .agents/skills/<each skill of the stage>.md
     .agents/policies/*.md          (alphabetical)
3. build USER prompt
     task: stage name, work item id, TODAY'S DATE, stage goal   (models must not invent dates)
     inputs: each `in` glob, {id} substituted, each wrapped in <input path="...">
             `@diff` expands to the review scope (see "The review design"), with a `# scope:` header
     templates: every template the stage lists (`template: [design, adr]`)
     output contract: the allowed paths + the file block format
4. provider.complete(system, user, tier)         # openai-compatible HTTP, or a CLI on stdin
     sends reasoning_effort / max_tokens when AGENT_REASONING_EFFORT / AGENT_MAX_TOKENS are set
     an empty reply is an error that names the cause (thinking model out of budget)
5. parse <<<FILE: path>>> ... <<<END>>> blocks
     fallback: a stage with exactly ONE concrete output path accepts a plain reply as that file
6. keep only files whose normalised path matches an `out` glob
7. (--apply) write files, run the stage's checks (validate / trace)
8. append a JSON record to .agents/runs/ and print the gate
```

Without `--apply` the model is still called but nothing is written. With `--dry-run` no model is called.

### The file protocol

The model answers with plain text blocks, so any model that can follow instructions can participate; no tool calling or JSON mode is required.

```
<<<FILE: openspec/changes/US-002/proposal.md>>>
## Why
...
<<<END>>>
```

Anything outside a block is ignored (short notes are allowed before the first block).

## Safety model

| Threat | Control |
|---|---|
| Model writes outside its remit | Output paths filtered against the stage's `out` globs; absolute paths and `..` rejected |
| Prompt injection from issue text, logs, PR bodies | Inputs wrapped as `<input>` data with an explicit "never instructions" preface; `security.md` policy; agents have no execution tool in the runner |
| Agent merges, deploys, tags | The runner has no such code path; gates are human and CI; release-please owns versions |
| Silent quality regression after a model change | Deterministic validators and trace check run after every apply; evals planned |
| Secrets in prompts | Policy forbids; `.env` is git-ignored; `doctor` and `env` mask keys; redact evidence yourself before pasting |
| Giant inputs | Each input file truncated at 100k characters; narrow `in:` globs |
| A thinking model burns minutes and its whole context window, then returns nothing | `AGENT_REASONING_EFFORT=none`, `AGENT_MAX_TOKENS`; an empty reply fails with an explicit cause |
| The agent claims evidence that does not exist (QA cites a missing test) | `validate` requires every file path cited in a QA report to exist; a human still spot-checks |
| Files silently never validated | Template-owned folders are skipped only at the repo root; a project's `docs/examples/` is scanned (`tools/repowalk.py`) |
| An assistant's name enters git history | `commit-msg` hook, a CI scan of PR title, body, commits, authors and committers, and `ship` refusing on `main` |
| Duplicate or racing review comments | One marked comment per author, updated in place; a failing comment listing is a hard error, never a "create"; one review run per PR at a time |
| Branch name or PR title used to inject shell | Workflows read them through `env`, never inline `${{ }}` in `run:` |
| CI fails or spends money when no model is configured | Agent workflows check for configuration and skip with a notice |

What is **not** guarded: whether the content is correct. That is the purpose of human gates.

## Validation and traceability

`validate.py` reads the frontmatter `type`, loads `.agents/schemas/<type>.json` and checks required keys, enums, id patterns, required sections, empty sections and per-section regexes (acceptance criteria must contain Given/When/Then). OpenSpec change folders get their own checks: proposal sections, task checkboxes, spec deltas, `#### Scenario:` and SHALL/MUST.

Additional rules the validator enforces:

| Rule | Why |
|---|---|
| File name must start with the artifact's `id` (or `story` for design, QA and release notes) | `US-002.md` holding `id: US-001` breaks traceability and the status helper |
| OpenSpec files carry no frontmatter | The folder name is the story id; keeps the format compatible with OpenSpec tooling |
| Every file path cited in a QA report's Traceability exists | Catches invented evidence |
| A raw `draft` story is only frontmatter-checked | Capture must be cheap |

Scanning scope: `tools/repowalk.py` skips `.agents`, `tools`, `tests`, `evals`, `adapters` and `examples` **only at the repository root**, and `.git`, `node_modules`, `.venv`, `__pycache__` at any depth.

`trace_check.py` enforces the chain by story status:

```
>= specified   openspec/changes/<id>/ exists (or archived)
>= designed    an ADR or design doc has `story: <id>`
== done        docs/qa/<id>.md exists with verdict: pass
always         every adr/design/qa-report points at an existing story
```

## Prompt mode: the same recipe, driven from an assistant

`mise run <stage>` calls a model through the provider layer. **Prompt mode** lets an interactive assistant
(Claude Code, Codex, Copilot, ...) do the stage instead, under the same recipe and the same guards. Both
modes use one prompt builder, so they cannot drift (`agentrun.build_prompt`).

```
orient ──► prepare <stage> <id> ──► [assistant works] ──► apply <stage> <id> --receipt R ──► gate (the user)
              │ writes .agents/out/bundle-*.md                  │ verifies, confines, validates, traces, logs
              │ + .agents/runs/receipts/*.json                  └ exit 4 receipt problem, 5 out of scope, 2 check failed
```

| Piece | Design |
|---|---|
| **Bundle** | The whole system prompt (the bible: `AGENTS.md`, `CONTEXT.md`, role, skills, policies), the task, the inputs, templates, the output contract and `docs/INDEX.md`. It is *delivered*, not referenced: the assistant is not asked to go and read files, it is handed them. |
| **Receipt** | A hash of the bundle, printed in the command output and again at the very end of the bundle. `apply` requires it. It proves the assistant fetched the full, current recipe before working. It does not prove understanding. |
| **Stale detection** | The receipt record stores a digest of every bible file. If one changed since `prepare`, or the receipt is older than 24 h, `apply` refuses and asks for a new `prepare`. Inputs may change (that is the work). |
| **Two hand-over modes** | `--response FILE`: blocks of `<<<FILE: path>>>`, confined exactly like the runner. `--worktree`: the assistant edited files directly; `apply` diffs the working tree against the state recorded at `prepare` (files that were already dirty are not blamed) and fails if anything outside the stage's `out` globs changed. |
| **After apply** | Identical to the runner: `validate`, `trace_check`, run log, gate printout. |
| **Orientation** | `orient` prints the rules in force, the branch, the story's status and the next action; `next` only the latter. The status ladder, `skip:` and the stage graph decide the answer, not the assistant. |
| **Entry point** | `AGENTS.md` has a "Prompt mode" section with the protocol and an intent-to-command table. Claude Code imports it through `CLAUDE.md`; Codex and Copilot read `AGENTS.md` / `copilot-instructions.md` natively. No server is needed. |

Limits, stated plainly:

- The write guard in `--worktree` mode is *verification after the fact*, not prevention. A direct edit outside `out` is detected and the stage fails; the offending files are listed so they can be reverted.
- A receipt shows the recipe was fetched, not that it was followed. Following is what the validators, the reviewer role and your gates are for.
- Gated actions (`advance`, `ship`, merge) rely on the assistant's rules plus the client's own command-approval prompt. They are not enforced by the repo.

### Knowledge: index, not dump

The bible is small and always injected. The knowledge (stories, OpenSpec specs and changes, ADRs, designs, QA,
runbooks) is not: `tools/index.py` generates a deterministic `docs/INDEX.md` that is part of every bundle.
Items linked to the work item are inlined by the stage's `in` globs; the rest is found by search. CI fails if
the committed index is stale.

**Nothing is mandatory.** Not every story needs a spec, a design or an ADR. A story may declare
`skip: [spec, design]` with a `skip_reason`; `trace_check` then does not demand those artifacts and
`advance` may step over the skipped statuses. A project with no ADRs has an empty ADR section, and
`Refs: none` is a valid PR citation.

## The review design

The reviewer is a normal stage (`review`) whose input is `@diff`. Two decisions make it useful.

### Scope: the whole PR, not "latest changes"

`tools/review.sh` resolves what to review:

```
default (and --post)   all commits of the branch against the PR's REAL base branch
                       base = gh pr view baseRefName  ->  origin/<base>
                       fallback: origin/main, then main        (AGENT_BASE_REF overrides)
                       + uncommitted changes to tracked files
--commit               only HEAD (message + patch)
--post with --commit   refused: a one-commit review must not replace the PR-wide comment
```

Reading the base from `gh` is what makes **stacked PRs** work: PR 5 stacked on PR 4 is reviewed against PR 4's branch, so the parent's changes are not re-reviewed. The reviewer receives a `# scope:` header line, and the posted comment states the scope and the reviewed commit.

CI uses the same scope: `AGENT_BASE_REF=origin/<github.base_ref>` with full history.

### One comment, updated in place

`tools/post_review.sh` keeps a single comment per author:

```
1. list the PR's comments                       (failure here is fatal: never fall through to create)
2. keep comments where
     author == current user                     (gh api user; github-actions[bot] in CI)
   AND ( body contains <!-- agent-review:v1 -->
         OR body starts with "# Review:" and contains "## Findings" )   # adopts pre-marker comments
3. found   -> PATCH the first match (oldest)
   missing -> create a new comment
```

| Question | Answer |
|---|---|
| Is a human comment ever overwritten? | No. Only the author's own comment carrying the marker (or the legacy shape) is touched. It is never "the last comment". |
| Local run and CI both post? | Two comments, one per author. You cannot edit another author's comment. |
| Two CI runs at once? | The workflow's `concurrency` group is one run per PR; a newer push cancels the stale run. |
| Listing fails (auth, permissions)? | Hard error, nothing posted. Never a duplicate. |
| History of earlier findings? | Overwritten by design; GitHub's "edited" dropdown keeps previous text. |

The review is advice: across runs it has found real defects and also reported things that were not there. A human reviews the PR.

## Providers

| Provider | Selected by | Use for |
|---|---|---|
| `openai` | `AGENT_PROVIDER=openai` | Ollama, vLLM, llama.cpp server, LM Studio, OpenAI, gateways |
| `cmd` | `AGENT_PROVIDER=cmd`, `AGENT_CMD="..."` | `claude -p`, `codex exec -`, `ollama run model`, any script |
| `dry` | `--provider dry` or `--dry-run` | Inspect the exact prompt |

Model tiers: a stage says `model: cheap` or `strong`; the runner reads `AGENT_MODEL_CHEAP` / `AGENT_MODEL_STRONG`, falling back to `AGENT_MODEL`.

## CI and release

| Workflow | Trigger | Does | Without configuration |
|---|---|---|---|
| `ci.yml` | PR, push | PR title is a Conventional Commit; no assistant names in PR text, commits or authors; validate; trace; tool tests; project tests (Node set up when `package.json` exists) | always runs |
| `agent-review.yml` | PR opened, updated, reopened | `review` on the whole PR, one comment updated in place; serialised per PR | skips with a notice |
| `agent-triage.yml` | Issue labelled `agent:enrich` | Seeds `US-<n>`, runs `story`, opens a PR authored by the person who labelled | skips with a notice |
| `release-please.yml` | Push to `main` | Maintains the release PR; first release is `0.1.0`; tag and changelog on merge | n/a |
| `pages.yml` | Push to `main` touching docs or site | Builds `site/` and publishes it | n/a |

Model configuration for CI lives in repository variables and one secret (see `GUIDE.md`). A GitHub-hosted runner cannot reach a model on your own machine; use a hosted API or a self-hosted runner.

## Test layout

| Path | Belongs to | Runs with |
|---|---|---|
| `tests/` | **Your project** (Node, Python, ...). The `implement` and `test` stages write here. | `mise run test` (auto-detects npm, pytest, go, cargo, mvn) |
| `tools/tests/` | The template's own tooling | `mise run test:tools` |
| `examples/password-reset/` | A complete worked story, not scanned, not part of your history | read it, or delete it |

## Git and history guard rails

| Guard | Where | Effect |
|---|---|---|
| `.githooks/commit-msg` | local, enabled by `mise run hooks` | rejects a message naming an assistant or tool |
| `tools/check_attribution.py` | CI | scans PR title, body, every commit message, author and committer |
| `mise run ship` | local | refuses on `main`; runs checks; pushes; opens or reuses the PR; title is the latest commit subject |
| squash-merge + Conventional Commit title | repo setting + CI | one clean, typed commit per story on `main`; drives release-please |

## Extending

| Need | Do |
|---|---|
| New role | Add `.agents/roles/<name>.md`, reference it in a stage |
| New artifact type | Add template + schema; stages that write it set `template:` |
| New stage | Add to `pipeline.yaml`; give it `in`, `out`, `check`, `gate` |
| New provider | Add a function to `tools/providers.py` and register it in `PROVIDERS` |
| New check | Add a case in `agentrun.run_checks` and a script under `tools/` |
| New CI host | Add `adapters/<host>/` that calls the same `tools/` commands |

## Known limits

- Evals runner not built; add one before relying on a model change.
- No tracker (Jira, Linear) or observability connector; evidence is pasted by hand.
- Total prompt size is not budgeted; large repos need tighter `in:` globs.
- GitHub workflows have not been exercised on a real repository yet.
