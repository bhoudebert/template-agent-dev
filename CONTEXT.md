# CONTEXT.md

Fill this in per project. Agents read it before every task.

## Product
One paragraph: what it is, who uses it, why it exists.

## Glossary
| Term | Meaning |
|---|---|
| Account | A registered user identity (example) |

## Stack and conventions
- Language/runtime:
- Build/test commands:
- Code style / lint:
- Branching and PR conventions: trunk-based. `main` + `feature/<US-id>-<slug>` per story, squash-merge, PR title = Conventional Commit (`feat(US-002): ...`).
- Versioning: SemVer, automated by release-please (release PR on `main`, tags `vX.Y.Z`, `CHANGELOG.md` generated). Details: `.agents/policies/git.md`.

## Constraints
- Compliance, performance, availability targets, supported platforms.

## Environments
- dev / staging / prod; how observability is reached (read-only).
