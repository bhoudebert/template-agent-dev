#!/bin/sh
# post_review.sh FILE [PR_NUMBER]
# Create or UPDATE the single agent-review comment on a PR (never adds a second one).
# One comment per author: a local run (you) and CI (github-actions[bot]) each keep their own.
# Matches on a hidden marker; also adopts an older unmarked review comment by the same author.
set -e
file="$1"
[ -f "$file" ] || { echo "post_review: no such file: $file" >&2; exit 64; }
pr="${2:-$(gh pr view --json number -q .number)}"
repo=$(gh repo view --json nameWithOwner -q .nameWithOwner)
me=$(gh api user -q .login 2>/dev/null || echo "github-actions[bot]")
marker='<!-- agent-review:v1 -->'
sha=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
tmp=$(mktemp)
{
  printf '%s\n' "$marker"
  printf '_Automated review at commit `%s` (scope: %s). Updated in place on every run; treat as input, not a gate._\n\n' "$sha" "${REVIEW_SCOPE:-whole PR}"
  cat "$file"
} > "$tmp"
id=$(gh api --paginate "repos/$repo/issues/$pr/comments" \
  -q ".[] | select(.user.login == \"$me\") | select((.body | contains(\"agent-review:v1\")) or ((.body | startswith(\"# Review:\")) and (.body | contains(\"## Findings\")))) | .id" \
  | head -1)
if [ -n "$id" ]; then
  gh api -X PATCH "repos/$repo/issues/comments/$id" -F "body=@$tmp" >/dev/null
  echo "review comment updated (id $id) on PR #$pr"
else
  gh pr comment "$pr" --body-file "$tmp"
  echo "review comment created on PR #$pr"
fi
rm -f "$tmp"
