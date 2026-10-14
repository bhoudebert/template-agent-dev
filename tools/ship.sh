#!/bin/sh
# ship.sh BASE [draft] [emergency]  - checks, push the current branch, open (or reuse) the PR.
#   draft="true"      open as a draft PR
#   emergency="true"  skip validate, trace, tests and evidence so a broken pipeline cannot block the fix
#   SHIP_PLAN_ONLY=1  run the checks, then print what would be pushed and stop
# Never skipped, even in an emergency: not on main (always a branch and a PR), and no assistant
# names in history. Stack PRs by passing the parent branch as BASE.
set -e
cd "$(dirname "$0")/.."
base="${1:-main}"; draft=""; [ "$2" = "true" ] && draft="--draft"
emergency="$3"
branch=$(git branch --show-current 2>/dev/null || git rev-parse --abbrev-ref HEAD 2>/dev/null || true)
if [ "$branch" = "main" ] || [ "$branch" = "master" ] || [ -z "$branch" ] || [ "$branch" = "HEAD" ]; then
  echo "refusing to ship from '${branch:-detached HEAD}': always a branch and a PR, even in an emergency." >&2
  echo "  git switch -c fix/<what-is-broken>      # then: mise run ship --emergency" >&2
  exit 1
fi

step() {
  "$@" || {
    echo "ship: '$*' failed." >&2
    echo "  If this check (or CI itself) is what is broken and you must ship the fix now: mise run ship --emergency" >&2
    exit 1
  }
}

if [ "$emergency" = "true" ]; then
  echo "EMERGENCY: skipping validate, trace, tests and evidence. Still enforced: branch + PR, no assistant names." >&2
else
  step python3 tools/validate.py
  step python3 tools/trace_check.py
  step sh tools/projecttest.sh
fi
git rev-parse --verify -q "$base" >/dev/null || git fetch -q origin "$base"
# Compare against the REMOTE base when there is one: a stale local branch of the same name would put
# commits that are already merged into this range.
ref="$base"
git rev-parse --verify -q "origin/$base" >/dev/null && ref="origin/$base"
python3 tools/check_attribution.py --range "$ref..HEAD"
if [ "$emergency" != "true" ]; then
  step env AGENT_BASE_REF="$ref" python3 tools/evidence.py
fi
if [ -n "$SHIP_PLAN_ONLY" ]; then
  echo "plan: would push '$branch' and open a PR against '$base'${emergency:+ (emergency)}"
  exit 0
fi
git push -u origin HEAD
if url=$(gh pr view --json url -q .url 2>/dev/null); then
  echo "PR already open, branch pushed: $url (draft -> ready: gh pr ready)"
else
  # title = latest commit subject (--fill alone would use the branch name when there are several commits).
  # body = commit subjects + Refs derived from the branch and commit messages; `Refs: none` is valid.
  refs=$(printf '%s\n%s\n' "$branch" "$(git log "$ref..HEAD" --format=%B)" \
    | grep -oE "$(python3 tools/config.py regex any)" | sort -u | paste -sd, - | sed 's/,/, /g')
  body=$(printf '## What and why\n\n%s\n\n## Refs\n\nRefs: %s\n' \
    "$(git log "$ref..HEAD" --reverse --format='- %s')" "${refs:-none}")
  if [ "$emergency" = "true" ]; then
    body=$(printf '%s\n\n## Emergency\n\nLocal checks were skipped to ship a fix. Follow up: a non-regression test, and a story or spec update if the behaviour was not covered.\n' "$body")
  fi
  # shellcheck disable=SC2086
  gh pr create --base "$base" --title "$(git log -1 --format=%s)" --body "$body" $draft
fi
