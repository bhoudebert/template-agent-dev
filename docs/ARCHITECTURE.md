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
     task: stage name, work item id, stage goal
     inputs: each `in` glob, {id} substituted, each wrapped in <input path="...">
     template: .agents/templates/<template>.md if the stage declares one
     output contract: the allowed paths + the file block format
4. provider.complete(system, user, tier)         # openai-compatible HTTP, or a CLI on stdin
5. parse <<<FILE: path>>> ... <<<END>>> blocks
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

What is **not** guarded: whether the content is correct. That is the purpose of human gates.

## Validation and traceability

`validate.py` reads the frontmatter `type`, loads `.agents/schemas/<type>.json` and checks required keys, enums, id patterns, required sections, empty sections and per-section regexes (acceptance criteria must contain Given/When/Then). OpenSpec change folders get their own checks: proposal sections, task checkboxes, spec deltas, `#### Scenario:` and SHALL/MUST.

`trace_check.py` enforces the chain by story status:

```
>= specified   openspec/changes/<id>/ exists (or archived)
>= designed    an ADR or design doc has `story: <id>`
== done        docs/qa/<id>.md exists with verdict: pass
always         every adr/design/qa-report points at an existing story
```

## Providers

| Provider | Selected by | Use for |
|---|---|---|
| `openai` | `AGENT_PROVIDER=openai` | Ollama, vLLM, llama.cpp server, LM Studio, OpenAI, gateways |
| `cmd` | `AGENT_PROVIDER=cmd`, `AGENT_CMD="..."` | `claude -p`, `codex exec -`, `ollama run model`, any script |
| `dry` | `--provider dry` or `--dry-run` | Inspect the exact prompt |

Model tiers: a stage says `model: cheap` or `strong`; the runner reads `AGENT_MODEL_CHEAP` / `AGENT_MODEL_STRONG`, falling back to `AGENT_MODEL`.

## CI and release

| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` | PR, push | PR title is a Conventional Commit; validate; trace; unit tests |
| `agent-review.yml` | PR opened or updated | Runs `review` stage on the diff, posts one comment |
| `agent-triage.yml` | Issue labelled `agent:enrich` | Seeds `US-<n>` from the issue, runs `story`, opens a PR |
| `release-please.yml` | Push to `main` | Maintains the release PR; tag and changelog on merge |

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
