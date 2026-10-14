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
# shellcheck disable=SC2086
# title = latest commit subject (--fill alone uses the branch name when there are several commits)
gh pr create --base "$base" --fill --title "$(git log -1 --format=%s)" $draft
