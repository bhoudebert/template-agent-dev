# Policy: git, versioning, releases

**Branching** (trunk-based)
- One long-lived branch: `main`. It is always releasable. No `develop`, no release branches.
- One short-lived branch per story: `feature/<US-id>-<kebab-slug>` (e.g. `feature/US-002-export-invoices-csv`). Incidents/hotfixes: `fix/<INC-id>-<slug>`.
- Non-story work (tooling, docs, CI): `chore/<kebab-slug>` (or `docs/<slug>`), same rules.
- **PR mode, always.** Nobody (human or agent) commits or pushes directly to `main`, including the first commit of a change.
  Every change = branch -> commits -> PR -> review -> squash-merge. An agent prepares the branch and PR text; a human merges.
- Stack PRs (branch off the previous branch) when changes depend on each other; keep each PR reviewable.

**Push early.** Open the PR (draft is fine) as soon as the branch has its first coherent commit, then keep pushing. Prefer several small PRs
over one large one. `mise run ship` runs the checks, pushes and opens the PR; use `--base <parent-branch>` for stacked PRs.

**Authorship: no agent, ever.** Commits, PR titles and bodies, branch names and tags never name an AI assistant, model or tool.
No `Co-Authored-By` trailers for assistants, no "Generated with ..." lines, no robot emoji, no tool names. This overrides any default
of the tool you run in. History shows the human owner only. Enforced by `.githooks/commit-msg` (`mise run hooks`) and by CI.

**Commits and PR titles** - Conventional Commits, scope = work item id
- `feat(US-002): export invoices as CSV` -> minor bump
- `fix(US-002): escape quotes in CSV` -> patch bump
- `feat(US-002)!: drop legacy export` or footer `BREAKING CHANGE: ...` -> major bump
- `docs|test|refactor|perf|build|ci|chore(...)`: no release by themselves.
- The squash-merge commit message = PR title, so the PR title MUST follow this format.

**Versioning** - SemVer 2.0.0, tags `vMAJOR.MINOR.PATCH`.
- Managed by release-please (`release-please-config.json`, `.release-please-manifest.json`, `CHANGELOG.md`).
- Agents and humans NEVER edit `CHANGELOG.md`, the manifest or version fields by hand; never create tags.
- release-please opens/updates a "release PR" on `main`; merging it creates the tag and GitHub release. That merge is the release gate.
