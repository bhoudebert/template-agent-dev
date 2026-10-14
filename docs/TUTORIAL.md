# Tutorial: your first story, end to end (Node.js)

You will take one small feature from a rough sentence to a released version, with an agent at every step and you at every gate.
Everything below was run for real on a local model (`gemma4:12b` through Ollama). Outputs vary from run to run; the *shape* of what happens does not.

Each step is tagged:

| Tag | Meaning |
|---|---|
| **[YOU]** | Manual. A person decides or edits. |
| **[AGENT]** | A role-agent runs (one command), writes files, then stops. |
| **[AUTO]** | A script or CI checks something. No model, no judgement. |

## The product we build

`shorty`, a tiny URL shortener, plain Node.js, no dependencies (`node:http`, `node:test`).

**Story US-001, "Shorten a URL":** `POST /shorten` returns a 6-character code, `GET /<code>` redirects, bad input is rejected clearly, the same URL twice returns the same code.

## Prerequisites

| Need | Check |
|---|---|
| Node.js 24 | `node --version` |
| [mise](https://mise.jdx.dev) | `mise --version` |
| git, and `gh` logged in for PRs | `gh auth status` |
| A model endpoint | Ollama running with a model pulled, e.g. `ollama pull gemma4:12b` |

---

## Part 0 - Set up the project (once)

### 0.1 Create your repository from the template **[YOU]**

Use the GitHub "Use this template" button, or clone and re-point the remote. Then enter the folder.

The template ships empty: no sample story, no sample code. A worked example lives in `examples/password-reset/` for comparison; delete that folder whenever you like.

### 0.2 Add the baseline app **[YOU]**

PR mode applies from the very first change. Make a branch and add four small files.

```sh
git switch -c chore/bootstrap
```

`package.json`

```json
{
  "name": "shorty",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "start": "node src/index.js",
    "test": "node --test"
  }
}
```

Use `node --test`, not `node --test tests/`: Node 24 treats the folder argument as a module and fails.

`src/app.js`

```js
import http from "node:http";

export function createApp() {
  return http.createServer((req, res) => {
    const url = new URL(req.url, "http://localhost");
    if (req.method === "GET" && url.pathname === "/health") {
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(JSON.stringify({ status: "ok" }));
    }
    res.writeHead(404, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: "not_found" }));
  });
}
```

`src/index.js`

```js
import { createApp } from "./app.js";

const port = Number(process.env.PORT ?? 3000);
createApp().listen(port, () => console.log(`shorty listening on ${port}`));
```

`tests/health.test.js`

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createApp } from "../src/app.js";

test("GET /health returns ok", async () => {
  const server = createApp().listen(0);
  const { port } = server.address();
  const res = await fetch(`http://127.0.0.1:${port}/health`);
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { status: "ok" });
  server.close();
});
```

### 0.3 Tell the agents about your project **[YOU]**

Edit `CONTEXT.md`. Every agent reads it before every task, so this is where your stack and conventions live.

```markdown
## Product
shorty: a tiny URL shortener HTTP API.

## Glossary
| Term | Meaning |
|---|---|
| Code | Short identifier, 6 chars of [a-zA-Z0-9], unique |
| Link | A stored mapping code -> target URL |

## Stack and conventions
- Language/runtime: Node.js 24, ES modules, no framework, no dependencies (node:http, node:test)
- Build/test commands: `npm test` (node --test)
- Code style: small modules in `src/`, one test file per feature in `tests/`, `node:assert/strict`

## Constraints
- In-memory storage is acceptable for now; no database.
- Responses are JSON except redirects.
```

### 0.4 Point the tools at your model **[YOU]**

```sh
cp .env.example .env
```

`.env` (git-ignored, loaded by mise):

```sh
AGENT_PROVIDER=openai
AGENT_BASE_URL=http://localhost:11434/v1
AGENT_MODEL=gemma4:12b
AGENT_REASONING_EFFORT=none
AGENT_MAX_TOKENS=16000
```

`AGENT_REASONING_EFFORT=none` matters for thinking models: without it, one stage on `gemma4:12b` spent six minutes and its entire context window reasoning, then returned nothing. With it, the same stage took eight seconds.

### 0.5 Turn on the guard rails and verify **[YOU]** then **[AUTO]**

```sh
mise trust
mise run hooks       # commit-msg hook: no assistant or tool names in history
mise run doctor      # python, git, hooks, endpoint, model served
mise run check       # validate + trace + your project tests (npm test)
```

Expect `all good`, `validate: 0 error(s)`, `trace_check: 0 problem(s)` and your test passing.

### 0.6 Ship the bootstrap **[YOU]**

```sh
git add -A && git commit -m "feat: bootstrap shorty app with health endpoint"
mise run ship          # checks, push, opens the PR
```

Merge it (squash). From now on every change repeats this branch, commit, ship, merge cycle.

---

## Part 1 - Capture the request

### 1.1 Create the item and its branch **[YOU]**

```sh
git switch main && git pull
mise run new Shorten a URL      # -> docs/stories/US-001.md  (status: draft)
mise run branch US-001          # -> feature/US-001-shorten-a-url
```

The id is allocated for you. The branch is created immediately, so nothing is ever committed on `main`.

### 1.2 Write the request in your own words **[YOU]**

Open `docs/stories/US-001.md`. Only the frontmatter is required while the status is `draft`; the body is free text:

```markdown
People want to turn a long link into a short one they can paste in a chat. They send the
long URL to our API and get back a short code, and when somebody opens the short link they
land on the original page. Links we cannot handle (not http/https, too long) must be
rejected clearly. Same long URL twice should not create two codes.
```

```sh
git add -A && git commit -m "docs(US-001): raw request"
mise run ship --draft           # push early; the PR is a draft, nothing is decided yet
```

---

## Part 2 - Story: from a paragraph to a testable story

### 2.1 Preview, then run **[AGENT]**

```sh
mise run story US-001 --dry     # prints the exact prompt; no model call, no cost
mise run story US-001 --plan    # calls the model, lists files, writes nothing
mise run story US-001           # writes docs/stories/US-001.md and runs the checks
```

The analyst role rewrites the file into the template: Story, Acceptance criteria (Given/When/Then), Edge cases, Out of scope, Open questions. Status becomes `enriched`.

### 2.2 Automatic check **[AUTO]**

`validate` runs right after the write: required sections present, non-empty, acceptance criteria contain Given/When/Then, status is a legal value. A failure prints `CHECK FAILED: ...` and exits 2; the files stay written so you can fix by hand.

### 2.3 The product owner gate **[YOU]**

Read the diff. The agent asked three genuinely useful questions:

```markdown
## Open questions
- What is the specific maximum character limit for a long URL?
- What are the specific error messages for "invalid protocol" and "too long"?
- Should the redirect be a 301 (Permanent) or 302 (Found)?
```

You answer them by editing the file. We chose 2048 characters, error codes `invalid_url` and `url_too_long`, and 302. The criteria become precise:

```markdown
- Given a valid HTTP/HTTPS URL, when a POST request is made with the URL, then the API
  returns 201 with JSON `{"code": "<6 chars>", "url": "<url>"}`.
- Given a URL longer than 2048 characters, ... returns 400 with `{"error": "url_too_long"}`.
```

Replace the open questions with "None. Decided by the product owner: ...". Then:

```sh
mise run validate
mise run advance US-001 approved       # guarded: refuses skipped steps
git add -A && git commit -m "docs(US-001): enrich and approve story"
git push
```

Try `mise run advance US-001 designed`: it refuses (`approved -> designed skips a step`). That guard is the point.

---

## Part 3 - Spec: behaviour as testable requirements

### 3.1 Run **[AGENT]**

```sh
mise run spec US-001
```

The spec-writer creates an OpenSpec change under `openspec/changes/US-001/`:

| File | Content |
|---|---|
| `proposal.md` | Why, What Changes, Impact |
| `tasks.md` | ordered checkbox tasks (validation, core logic, endpoints, error handling) |
| `specs/api/spec.md` | `SHALL` requirements, each with `#### Scenario:` WHEN/THEN |

### 3.2 Automatic check **[AUTO]**

On the real run the model added `story:`/`id:` frontmatter to the OpenSpec files and `validate` refused:

```text
CHECK FAILED: openspec/changes/US-001/proposal.md: OpenSpec files must not have frontmatter
```

That rule is now in the validator and in the prompts, but the lesson holds: when a check fails, the files are on disk, so you fix or rerun.

### 3.3 The spec gate **[YOU]**

This is where a person adds value. Compare the story's edge cases with the spec's scenarios. The agent covered every acceptance criterion but **missed "malformed JSON" and "empty URL"**. You add them by hand:

```markdown
### Requirement: Malformed Request Body
The system SHALL reject a POST body that is not valid JSON or has no `url` string.

#### Scenario: Malformed JSON
- **WHEN** a POST request is made with a body that is not valid JSON
- **THEN** the API returns 400 with `{"error": "invalid_url"}`
```

```sh
mise run advance US-001 specified      # requires openspec/changes/US-001/ to exist
git add -A && git commit -m "docs(US-001): spec" && git push
```

---

## Part 4 - Design: decisions with reasons

### 4.1 Run **[AGENT]**

```sh
mise run design US-001
```

The architect writes `docs/architecture/US-001.md` (components, data flow, risks, test strategy) and one ADR per real decision. Here: `ADR-0001-code-generation.md`, comparing deterministic hashing (collision-prone at 6 characters) with random generation plus a collision check.

### 4.2 The tech lead gate **[YOU]**

| Check | What we found |
|---|---|
| Are the options real? | Yes: hashing vs random + collision check, with honest cons |
| Does it match the spec? | Yes |
| Anything invented? | The ADR `date:` was made up. The runner now injects today's date into every prompt, and the design stage gets both the design and ADR templates |
| Any risk the agent got wrong? | It worried about concurrent requests claiming the same code. In Node the check-then-set is synchronous, so the real rule is "no `await` between check and set". We wrote that into the risk |

Accept the ADR yourself (`status: accepted`), then:

```sh
mise run validate
mise run advance US-001 designed
git add -A && git commit -m "docs(US-001): design and ADR-0001" && git push
```

`trace_check` now enforces that an ADR or design references `US-001`.

---

## Part 5 - Implement: where you and the agent alternate

### 5.1 Run **[AGENT]**

```sh
mise run implement US-001 --plan    # what would it write?
mise run implement US-001           # ~40 s on a 12B local model
```

It produced `src/validator.js`, `src/code-generator.js`, `src/link-store.js`, an extended `src/app.js`, `tests/shorten.test.js`, and ticked **every** task in `tasks.md`.

### 5.2 Never trust the ticks **[YOU]**

The runner does not run your tests. You do:

```sh
npm test
```

First run, honestly:

```text
ℹ tests 10   ℹ pass 6   ℹ fail 3   (and the test file never exited)
```

Triage, which is the real work of this stage:

| Symptom | Cause | Whose fault | Fix |
|---|---|---|---|
| `GET /:code` returned 404 | `pathname.length === 6`, but `/abc123` has 7 characters | App bug | Match `^\/[a-zA-Z0-9]{6}$` and take `slice(1)` |
| URL-too-long test got `invalid_url` | Test used `"a".repeat(2049)`, which fails the protocol check first | Test bug | Use `"https://example.com/" + "a".repeat(2049)` |
| Trimming test got 200 instead of 201 | Shared in-memory store: the URL was already stored by another test | Test bug | Use a unique URL |
| Test file hung | `fetch` keep-alive connections keep the server open | Test bug | `server.closeAllConnections()` before `server.close()` |
| Redirect test hung | `fetch` followed the 302 to the real `target.com` | Test bug | `fetch(..., { redirect: "manual" })` |

After the fixes: 9 of 9 pass.

```sh
mise run advance US-001 implemented
git add -A && git commit -m "feat(US-001): shorten and redirect endpoints" && git push
```

### 5.3 Rules of thumb

- One task per run keeps diffs readable. Use `--plan` first when the task is big.
- The spec wins over the code. If the code is right and the spec wrong, change the spec in its own commit.
- If the agent keeps failing the same way, the task is too big: split it in `tasks.md`.
- Generated tests need the same review as generated code. You will meet inverted assertions and missing cleanup.

---

## Part 6 - Test: cover every scenario

### 6.1 Run **[AGENT]**

```sh
mise run agent:test US-001       # `mise run test` is YOUR project's test command
```

`mise run test` auto-detects your stack (`npm test`, pytest, go, cargo, mvn). The agent stage is `agent:test`.

It added `tests/edge-cases.test.js` (empty URL, whitespace-only, non-string URL, code uniqueness).

### 6.2 Review the agent's tests **[YOU]**

One assertion was inverted: `assert.ok(codes.has(data.code), "Code should be unique")`. It fails on correct code, and because the failure skipped cleanup the process hung. Fix: `assert.ok(!codes.has(data.code), ...)`.

```sh
npm test      # 13 pass
git add -A && git commit -m "test(US-001): edge cases and code uniqueness" && git push
```

---

## Part 7 - QA: an independent verdict

### 7.1 Run **[AGENT]**

```sh
mise run qa US-001
```

It writes `docs/qa/US-001.md`: a traceability table (every criterion and scenario to evidence), findings, a verdict, and a mandatory **Not verified** section.

### 7.2 Automatic check **[AUTO]**

`validate` requires the report's shape, and (since this run) that every file path cited as evidence exists.

### 7.3 The QA gate **[YOU]**

Do not accept "pass" on sight. Spot-check the evidence. Here the report claimed the "exactly 2048 characters" criterion was covered "via logic check". There was no such test:

```sh
grep -n "2048" tests/*.js      # only the 2049 test
```

So you add the missing boundary test, and correct the report (evidence file, plus a finding noting what was wrong). Then:

```sh
npm test                               # 14 pass
mise run advance US-001 done           # requires qa-report with verdict: pass
git add -A && git commit -m "test(US-001): 2048 boundary; qa report corrected" && git push
```

---

## Part 8 - Review and merge

### 8.1 Second pair of eyes **[AGENT]**

```sh
mise run review            # diff of this branch vs main (+ uncommitted changes), printed
mise run review --post     # same, and comment it on the open PR
```

The review is also written to `.agents/out/review-<id>.md`.

How it behaves, so nothing surprises you:

| Question | Answer |
|---|---|
| What does it review? | The **whole PR**: every commit against the PR's real base branch (stack-aware), plus uncommitted tracked changes. `mise run review --commit` reviews only the last commit. |
| Will it add a new comment each run? | No. `--post` (and CI) update **one** marked comment in place. Your own comments are never touched, and it is never "the last comment". |
| Can I post a last-commit review? | No, it is refused: it would replace the PR-wide review. |
| What if it cannot list comments? | It posts nothing and says why. It never falls back to a duplicate. |
| In CI? | The same stage runs on each PR, once a model is configured there; otherwise it skips with a notice. | Its quality is uneven: across two runs it once flagged the unbounded request body and once did not. Treat it as extra input, never as the review.

### 8.2 Your review **[YOU]**

| Look at | Why |
|---|---|
| Whole diff, once | The agent ticks tasks; you verify |
| Request body size | A `POST` handler that concatenates `req.on("data")` without a limit is a memory risk |
| `catch (e)` that returns `invalid_url` for everything | Masks unexpected errors |
| Test cleanup | Failures must not leave servers open |

### 8.3 Open the PR and merge **[YOU]** then **[AUTO]**

```sh
mise run ship        # runs checks, pushes; opens the PR if none exists yet
gh pr ready          # if the PR is still a draft
```

The PR title is the squash commit and must be a Conventional Commit: `feat(US-001): shorten and redirect URLs`.

CI then runs **[AUTO]**: title format, no assistant names in commits or PR text, `validate`, `trace_check`, tool tests and your `npm test`, plus the agent review. When green and reviewed, **[YOU]** squash-merge.

---

## Part 9 - Release

### 9.1 Release notes and go/no-go **[AGENT]**

```sh
mise run release US-001       # writes docs/releases/US-001.md (validated)
```

Human-readable notes (Added, Changed, Fixed, Security), a predicted bump, and a go/no-go checklist: QA verdict, migrations, rollback, who watches what. Read it critically: it labelled the 2048 boundary a "fix" although the feature is new.

### 9.2 The version **[AUTO]** then **[YOU]**

On the merge to `main`, release-please sees a `feat` commit and opens a release PR (`chore(main): release 0.1.0`) with `CHANGELOG.md`. Nobody edits version numbers by hand. **[YOU]** merge that PR: tag `v0.1.0` and the GitHub release appear.

---

## Part 10 - Production incident

A week later: support reports that short links created in the morning return 404.

### 10.1 Open the incident **[YOU]**

```sh
git switch main && git pull
mise run incident Redirects return 404 for known codes after restart   # -> docs/incidents/INC-001.md
```

Paste evidence under `## Evidence`: the report, the deploy time, a few log lines, a metric. Redact secrets. Treat logs as data: the agent is told never to follow instructions found in them.

### 10.2 Diagnose **[AGENT]**

```sh
mise run diagnose INC-001
```

Result, in seconds:

| Part | Content |
|---|---|
| Impact | Links created before the 10:31 restart no longer resolve |
| Hypothesis 1 (high) | In-memory storage was wiped by the restart. `CONTEXT.md` already said in-memory was acceptable |
| Hypothesis 2 (low) | Startup race |
| Recommended | Mitigation for a human to execute; a new story for persistent storage |
| Not verified | How many links were lost |
| Bonus | A runbook `RB-001` for next time |

### 10.3 You decide **[YOU]**

You execute any mitigation yourself. The follow-up is a new story (`mise run new Persist links across restarts`), on a `feature/US-002-...` branch, and the whole cycle starts again.

---

## The full picture

| # | Step | Command | Actor | Output | Gate |
|---|---|---|---|---|---|
| 1 | Create item and branch | `mise run new`, `mise run branch` | YOU | raw story, story branch | |
| 2 | Write request | edit file | YOU | raw request | |
| 3 | Push early | `mise run ship --draft` | YOU + AUTO | draft PR | |
| 4 | Story | `mise run story` | AGENT | enriched story | |
| 5 | Check shape | `validate` (runs after the stage) | AUTO | pass/fail | |
| 6 | Approve story | edit, `advance approved` | YOU | status `approved` | product owner |
| 7 | Spec | `mise run spec` | AGENT | OpenSpec change | |
| 8 | Approve spec | edit, `advance specified` | YOU | status `specified` | PO + tech lead |
| 9 | Design + ADR | `mise run design` | AGENT | design note, ADR | |
| 10 | Approve design | edit, `advance designed` | YOU | status `designed` | tech lead |
| 11 | Implement, one task at a time | `mise run implement` | AGENT | code, tests, ticks | |
| 12 | Run tests, review diff, fix | `npm test`, `git diff` | YOU | green tests | you |
| 13 | Advance | `advance implemented` | YOU | status `implemented` | |
| 14 | Add tests | `mise run agent:test` | AGENT | more tests | |
| 15 | Review those tests | `npm test` | YOU | green | you |
| 16 | QA | `mise run qa` | AGENT | QA report | |
| 17 | Verify evidence | `grep`, read | YOU | corrected report | QA or PO |
| 18 | Done | `advance done` | YOU + AUTO | trace checked | |
| 19 | Agent review | `mise run review` / CI | AGENT | PR comment | |
| 20 | Human review, merge | PR | YOU | squash commit on `main` | merge |
| 21 | CI | PR checks | AUTO | green/red | |
| 22 | Release notes | `mise run release` | AGENT | notes + go/no-go | release manager |
| 23 | Version, tag, changelog | release PR | AUTO then YOU | `v0.1.0` | merge release PR |
| 24 | Incident | `mise run incident`, `diagnose` | YOU, AGENT | report, runbook | on-call |

### What is automated, what is not

| Automated | Always manual |
|---|---|
| Prompt assembly, output confinement, file writing | Writing the request |
| Schema, section and traceability checks | Answering open questions, approving each gate |
| Status guard (`advance`) | Running and reading your tests |
| Commit message and PR title rules, no assistant names | Spotting what the agent missed or overclaimed |
| CI checks, agent PR review | Merging PRs |
| Versioning, changelog, tags (release-please) | Deciding to release, executing mitigations |

## What went wrong on the real run (and what we changed)

An honest list, because it is the best preparation for your own first run. Each item is now fixed in the template or documented here.

| What happened | Fix |
|---|---|
| Sample story in the template collided with the first real `US-001` | Moved to `examples/` |
| `mise run test` ran the template's tests, not the project's | Auto-detects npm, pytest, go, cargo, mvn |
| `node --test tests/` failed on Node 24 | Use `node --test` |
| Model put frontmatter into OpenSpec files | Validator rejects it; prompts say so |
| Design note drifted because only the ADR template was supplied | Stage supplies both templates |
| Model invented a date | Prompt carries today's date |
| A thinking model burned 6 minutes and returned nothing | `AGENT_REASONING_EFFORT=none`, `AGENT_MAX_TOKENS`, and a clear error message |
| A stage replied in plain markdown instead of a file block | Single-output stages accept the plain reply |
| Release notes and runbooks had no schema | Added schemas and templates |
| QA cited a test that did not exist | Validator checks cited files exist; you still spot-check |
| Agent ticked all tasks while 3 tests failed | You run the tests; ticks are claims, not proof |

## Troubleshooting

| Symptom | Cause | Do |
|---|---|---|
| Stage takes minutes, then `model returned no text` | Thinking model exhausted its budget | `AGENT_REASONING_EFFORT=none`, `AGENT_MAX_TOKENS=16000` |
| `no files in response` | Model ignored the output format | Retry; use a stronger model; for a one-file stage the plain reply is accepted |
| `CHECK FAILED` after a write | Output does not match its schema | Fix the file by hand, or rerun |
| `npm test` never exits | Server left open by a test | `closeAllConnections()`, `t.after(...)` cleanup |
| `mise run ship` refuses | You are on `main` | `mise run branch <id>` first |
| Commit rejected by the hook | Message names an assistant or tool | Reword it |
