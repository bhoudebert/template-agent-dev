#!/bin/sh
# ship.sh BASE [true]  - checks, push the current branch, open the PR (draft if 2nd arg is "true").
# PR mode: refuses to run on main. Stack PRs by passing the parent branch as BASE.
set -e
cd "$(dirname "$0")/.."
base="${1:-main}"; draft=""; [ "$2" = "true" ] && draft="--draft"
branch=$(git branch --show-current)
if [ "$branch" = "main" ] || [ -z "$branch" ]; then
  echo "refusing to ship from '${branch:-detached HEAD}': PR mode. Create a branch (mise run branch <id>)." >&2
  exit 1
fi
python3 tools/validate.py
python3 tools/trace_check.py
sh tools/projecttest.sh
git rev-parse --verify -q "$base" >/dev/null || git fetch -q origin "$base"
python3 tools/check_attribution.py --range "$base..HEAD"
git push -u origin HEAD
if url=$(gh pr view --json url -q .url 2>/dev/null); then
  echo "PR already open, branch pushed: $url (draft -> ready: gh pr ready)"
else
  # title = latest commit subject (--fill alone uses the branch name when there are several commits)
  # shellcheck disable=SC2086
  # body: what changed (commit subjects) + Refs derived from the branch and commit messages.
  # `Refs: none` is a valid answer: not every change has a story, spec or ADR.
  refs=$(printf '%s\n%s\n' "$branch" "$(git log "$base..HEAD" --format=%B)" \
    | grep -oE '(US|INC)-[0-9]+|ADR-[0-9]{4}' | sort -u | paste -sd, - | sed 's/,/, /g')
  body=$(printf '## What and why\n\n%s\n\n## Refs\n\nRefs: %s\n' \
    "$(git log "$base..HEAD" --reverse --format='- %s')" "${refs:-none}")
  gh pr create --base "$base" --title "$(git log -1 --format=%s)" --body "$body" $draft
fi
