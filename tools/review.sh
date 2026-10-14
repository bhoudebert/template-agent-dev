#!/bin/sh
# review.sh [ID] [post]  - run the reviewer on this branch's diff, locally, and print it.
#   ID    US-NNN / INC-NNN; default: found in the branch name, else PR-<n>, else LOCAL
#   post  "true" posts the review as a comment on the branch's open PR
# The diff is the branch against main plus any uncommitted changes to tracked files.
set -e
cd "$(dirname "$0")/.."
branch=$(git branch --show-current)
id="$1"
if [ -z "$id" ]; then
  id=$(printf '%s' "$branch" | grep -oE '(US|INC)-[0-9]+' | head -1 || true)
fi
if [ -z "$id" ] && command -v gh >/dev/null 2>&1; then
  n=$(gh pr view --json number -q .number 2>/dev/null || true)
  [ -n "$n" ] && id="PR-$n"
fi
id="${id:-LOCAL}"
if [ -z "$AGENT_BASE_REF" ]; then
  if git rev-parse --verify -q origin/main >/dev/null; then AGENT_BASE_REF=origin/main
  elif git rev-parse --verify -q main >/dev/null; then AGENT_BASE_REF=main
  else echo "no main branch to diff against; set AGENT_BASE_REF" >&2; exit 1; fi
  export AGENT_BASE_REF
fi
if [ "$branch" = "main" ] && git diff --quiet HEAD; then
  echo "nothing to review: you are on main with no changes" >&2
  exit 1
fi
echo "review: id=$id base=$AGENT_BASE_REF branch=${branch:-detached}" >&2
python3 tools/agentrun.py run review --id "$id" --apply
out=".agents/out/review-$id.md"
echo
echo "================ $out ================"
cat "$out"
if [ "$2" = "true" ]; then
  sh tools/post_review.sh "$out"
fi
