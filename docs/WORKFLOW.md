# Workflow: who does what, and when

This page answers one question: **right now, is it the agent's turn or mine?**

## The one-minute version

1. You write a rough request. An agent turns it into a precise story.
2. A person approves it. Agents then write the spec, the design, the code, the tests and the QA report, one stage at a time.
3. After **every** stage a person reads the result and decides. Nothing moves forward on its own.
4. Deterministic scripts check the shape of every artifact and the chain between them.
5. **PR mode, always**: every change travels on a branch and reaches `main` through a reviewed PR. Merging and releasing are done by humans and release-please, never by an agent.

```
you: request -> agent: story -> YOU approve -> agent: spec -> YOU approve -> agent: design -> YOU approve
  -> agent: implement (loop with you) -> agent: test -> agent: qa -> CI + agent: review -> YOU merge
  -> release-please PR -> YOU merge -> tag vX.Y.Z
```

## Who acts

| Actor | Does | Never does |
|---|---|---|
| **Agent** (one role per stage) | Reads inputs, writes the artifacts of its stage into allowed paths | Merge, deploy, tag, edit versions, touch production, approve its own work |
| **You / the team** | Write requests, review diffs, answer open questions, bump status, commit, merge | Edit the validators to make a check pass |
| **Scripts** (`validate`, `trace_check`) | Fail loudly when an artifact is malformed or the chain is broken | Judge whether the content is *right* |
| **CI** | Runs scripts and tests, checks PR title, runs the agent reviewer | Merge |
| **release-please** | Opens the release PR, computes SemVer, writes `CHANGELOG.md`, tags | Run without a merged release PR |

## Small stories skip stages

Not every story needs a spec, a design or an ADR. A story that does not (a copy change, a config tweak) declares
`skip: [spec, design]` and a `skip_reason` in its frontmatter; `mise run skip US-003 spec,design --reason "copy fix"` writes both lines for you (`mise run skip US-003 none` clears them). The story stage keeps them when it rewrites the file. `mise run next` then points straight to the
next stage that applies, and `mise run advance US-002 designed` may step over the skipped statuses. QA, review
and the PR gate still apply.

## The status ladder

The story file's `status:` is the single source of truth for where a work item is.

```
draft -> enriched -> approved -> specified -> designed -> implemented -> done
```

| Status | Meaning | Who sets it | Guard |
|---|---|---|---|
| `draft` | Raw request | you (`mise run new`) | Only frontmatter is validated |
| `enriched` | Agent produced the full story | the story agent | Sections + Given/When/Then required |
| `approved` | Product owner accepts the story | you (`mise run advance US-002 approved`) | No skipped steps |
| `specified` | OpenSpec change reviewed | you | `openspec/changes/US-002/` must exist |
| `designed` | Design/ADR reviewed | you | An ADR or design with `story: US-002` must exist |
| `implemented` | All tasks done, CI green | you | none beyond order |
| `done` | QA passed | you | `docs/qa/US-002.md` with `verdict: pass` |

`mise run advance` refuses a skipped step or a broken chain and restores the file.

## Stage by stage

Each card: what you do **before**, what the **agent** does, what you **check** at the gate, what you do **after**.

### 1. Story (analyst)
- **Before**: `mise run new "Export invoices as CSV" --text "Finance wants all invoices of a month as CSV, with a VAT column."` creates `docs/stories/US-NNN.md` (the next free id) holding your title and request. Without `--text` it holds only the title and a placeholder: open the file and write the request in your own words. Then immediately `mise run branch US-NNN` so you are off `main` before anything is committed (PR mode: nothing is ever committed on `main`).
- **Agent**: `mise run story US-002`. It **reads** your story file (the request you wrote) and `CONTEXT.md`, then **rewrites that same file** into Story, Acceptance criteria (Given/When/Then), Edge cases, Out of scope, Open questions. If the file still holds only the title, it refuses (`NEEDS INPUT`, exit 6) rather than invent a story.
- **Check** (product owner): are the criteria what you meant? Answer every open question. Is it small enough to ship alone?
- **After**: `mise run advance US-002 approved`. Commit.

### 2. Spec (spec-writer)
- **Before**: you are on the story branch `feature/US-002-<slug>`, and the approved story is committed there.
- **Agent**: `mise run spec US-002`. Writes `openspec/changes/US-002/` (`proposal.md`, `tasks.md`, `specs/*/spec.md`).
- **Check** (PO + tech lead): every acceptance criterion maps to a `#### Scenario:`; requirements say SHALL/MUST; tasks are small and ordered.
- **After**: `mise run advance US-002 specified`. Commit `docs(US-002): spec`.

### 3. Design (architect)
- **Agent**: `mise run design US-002`. Writes `docs/architecture/US-002.md` and one `ADR-NNNN-*.md` per real decision.
- **Check** (tech lead): are options honest? Does it contradict an accepted ADR? Edit the ADR `status:` to `accepted` when you agree.
- **After**: `mise run advance US-002 designed`.

### 4. Implement (developer) - where you work most
This is a loop, not a step. See [the developer loop](#the-developer-loop).
- **After** all boxes in `tasks.md` are ticked and your tests are green: `mise run advance US-002 implemented`.

### 5. Test (test-engineer)
- **Agent**: `mise run agent:test US-002`. Adds integration, edge and negative tests; lists uncovered scenarios.
- **Check**: run the suite yourself. Reject any deleted or weakened test.

### 6. QA (qa)
- **Agent**: `mise run qa US-002`. Writes `docs/qa/US-002.md`: traceability table, findings, verdict, and what was *not* verified.
- **Check** (QA or PO): read `Not verified`. A `fail` or `blocked` sends you back to implement.
- **After** on `pass`: `mise run advance US-002 done` (needs the QA report with `verdict: pass`).

### 7. Review (reviewer) and merge
- **Agent**: runs on the PR in CI (`agent-review`, only when a model is configured there), or locally with `mise run review` (the whole PR against its base branch; `--post` to comment on the PR, `--commit` for just the last commit). One comment, findings ranked blocker/major/minor/nit.
- **Scope**: the whole PR (every commit against its real base branch), not just the latest push. `--commit` reviews only the last commit and is never posted.
- **The comment**: one comment per author, updated in place on every run; yours and others' comments are never overwritten.
- **Check**: you are the reviewer; the agent is a second pair of eyes that is sometimes wrong. Verify each finding, fix what is real.
- **After**: squash-merge into `main`. The PR title is the commit and must be a Conventional Commit, e.g. `feat(US-002): export invoices as CSV`.

### 8. Release
- **Agent**: `mise run release US-002` writes human release notes, the predicted bump and a go/no-go checklist.
- **release-please** opens or updates the release PR on `main`. Merging it creates the tag and the GitHub release.
- **Check**: rollback plan, migrations, monitoring owner. Then merge the release PR.

### 9. Diagnose (sre) - production incident
- **Before**: `mise run incident "Checkout 500s"`, then paste logs, metrics and recent deploys under `## Evidence` (redact secrets).
- **Agent**: `mise run diagnose INC-001`. Ranked hypotheses, evidence for and against, mitigation proposals, and what is unknown.
- **Check** (on-call): a human executes any mitigation. If root cause needs code, create a story; it enters the normal flow on a `fix/INC-001-<slug>` branch.

## The developer loop

The only stage where agent and developer alternate quickly.

```
1. mise run implement US-002 --plan     # see what it would write
2. mise run implement US-002            # write files, run checks
3. git diff                             # YOU read every line
4. run the project's tests              # the runner does not run them
5. fix by hand or rerun with a sharper task note in tasks.md
6. git commit -m "feat(US-002): <task>" # one task, one commit
7. repeat until every box in tasks.md is checked
```

Rules of thumb:

- One task at a time keeps diffs reviewable and prompts small.
- If the code and the spec disagree, **the spec wins until a person changes it**. Stop, fix the spec in its own commit, rerun.
- If the agent keeps failing the same way, the task is too big. Split it in `tasks.md`.
- Never ask the agent to "make the tests pass" by editing tests. Reject that diff.

## Branches, commits, versions

| Thing | Convention |
|---|---|
| Long-lived branch | `main` only, always releasable |
| Work branch | `feature/<US-id>-<slug>` per story; `fix/<INC-id>-<slug>` for incidents |
| Commit / PR title | Conventional Commits, scope = work item id: `feat(US-002): ...` |
| Authorship | History shows the human owner only: no assistant or tool names, no `Co-Authored-By` for an AI, no "Generated with" lines. Hook + CI enforce it |
| Pushing | Push early, small PRs: `mise run ship` (checks, push, open PR; `--draft`, `--base <parent>` for stacks) |
| Breaking change | `feat(US-002)!:` or footer `BREAKING CHANGE:` |
| Version | SemVer by release-please; tags `vX.Y.Z`; nobody edits `CHANGELOG.md` |

## When a check fails

| Failure | Meaning | You do |
|---|---|---|
| `validate`: missing section / bad enum | Artifact does not match its schema | Fix the artifact or rerun the stage; never loosen the schema to pass |
| `trace_check`: status without artifact | You moved status before the artifact exists | Revert the status or create the artifact |
| Stage prints `REJECTED (outside allowed paths)` | Model tried to write elsewhere | Nothing: it was discarded. Rerun if the output is missing |
| Stage prints `no files in response` | Model ignored the output format | Retry, use a stronger model, or simplify the task |
| CI: PR title rejected | Not a Conventional Commit | Rename the PR |

## Definition of done for a story

- [ ] Story approved; every open question answered
- [ ] Every acceptance criterion has a spec scenario and a test
- [ ] ADR accepted for each real decision
- [ ] `tasks.md` fully checked
- [ ] `mise run check` is green
- [ ] QA report `verdict: pass`, `Not verified` read by a human
- [ ] PR squash-merged with a Conventional Commit title
- [ ] Release PR merged when it is time to ship

## RACI

| Stage | Agent | Product owner | Tech lead | Dev | QA | On-call |
|---|---|---|---|---|---|---|
| story | R | A | C | I | I | |
| spec | R | A | A | C | I | |
| design | R | C | A | C | | |
| implement | R | I | C | A | | |
| test | R | | C | A | C | |
| qa | R | C | | I | A | |
| review | R | | A | C | | |
| release | R | C | A | I | C | I |
| diagnose | R | I | C | C | | A |

R = produces the draft, A = accountable for the gate, C = consulted, I = informed.
