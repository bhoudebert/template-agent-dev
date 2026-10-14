#!/bin/sh
# review.sh [ID] [post] [commit]
#   default scope: the WHOLE branch/PR: every commit against the PR's base branch
#                  (read from gh, so stacked PRs work) plus uncommitted tracked changes
#   commit="true": only the last commit (HEAD). Cannot be combined with post: a one-commit
#                  review must never replace the PR-wide comment.
#   post="true":   create/update the single review comment on the branch's open PR
# Env: AGENT_BASE_REF overrides the base.
set -e
cd "$(dirname "$0")/.."
branch=$(git branch --show-current 2>/dev/null || git rev-parse --abbrev-ref HEAD 2>/dev/null || true)
[ "$branch" = "HEAD" ] && branch=""
id="$1"; post="$2"; commit_mode="$3"

if [ "$commit_mode" = "true" ] && [ "$post" = "true" ]; then
  echo "refusing --post with --commit: the PR comment must describe the whole PR. Drop --commit to post." >&2
  exit 1
fi

if [ -z "$id" ]; then
  id=$(printf '%s' "$branch" | grep -oE '(US|INC)-[0-9]+' | head -1 || true)
fi
pr_number=""; pr_base=""
if command -v gh >/dev/null 2>&1; then
  pr_number=$(gh pr view --json number -q .number 2>/dev/null || true)
  pr_base=$(gh pr view --json baseRefName -q .baseRefName 2>/dev/null || true)
fi
if [ -z "$id" ] && [ -n "$pr_number" ]; then id="PR-$pr_number"; fi
id="${id:-LOCAL}"

if [ "$commit_mode" = "true" ]; then
  export AGENT_DIFF_COMMIT=HEAD
  scope="last commit $(git rev-parse --short HEAD) only"
else
  if [ -z "$AGENT_BASE_REF" ]; then
    [ -n "$pr_base" ] && git fetch -q origin "$pr_base" 2>/dev/null || true
    for cand in "origin/${pr_base:-main}" "${pr_base:-main}" origin/main main; do
      if git rev-parse --verify -q "$cand" >/dev/null; then AGENT_BASE_REF="$cand"; break; fi
    done
    [ -n "$AGENT_BASE_REF" ] || { echo "no base branch to diff against; set AGENT_BASE_REF" >&2; exit 1; }
    export AGENT_BASE_REF
  fi
  n=$(git rev-list --count "$AGENT_BASE_REF..HEAD" 2>/dev/null || echo "?")
  scope="whole branch: $n commit(s) vs $AGENT_BASE_REF"
  if [ "$branch" = "main" ] && git diff --quiet HEAD && [ "$n" = "0" ]; then
    echo "nothing to review: you are on main with no changes" >&2
    exit 1
  fi
fi
export AGENT_DIFF_SCOPE="$scope" REVIEW_SCOPE="$scope"

echo "review: id=$id scope=[$scope] branch=${branch:-detached}" >&2
python3 tools/agentrun.py run review --id "$id" --apply
out=".agents/out/review-$id.md"
echo
echo "================ $out ================"
cat "$out"
if [ "$post" = "true" ]; then
  sh tools/post_review.sh "$out" "$pr_number"
fi
