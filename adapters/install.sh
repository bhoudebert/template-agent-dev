#!/bin/sh
# Install thin pointers so each tool/CI host finds the vendor-neutral content.
# usage: adapters/install.sh [github] [tools]
set -e
cd "$(dirname "$0")/.."
for target in "$@"; do
  case "$target" in
    github)
      mkdir -p .github/workflows
      cp adapters/github/workflows/*.yml .github/workflows/
      ;;
    tools)
      printf '@AGENTS.md\n' > CLAUDE.md                          # Claude Code
      mkdir -p .github .cursor/rules
      printf 'Follow AGENTS.md at the repository root.\n' > .github/copilot-instructions.md   # Copilot
      printf -- '---\nalwaysApply: true\n---\nFollow AGENTS.md at the repository root.\n' > .cursor/rules/agents.mdc  # Cursor
      ;;
    *) echo "unknown target: $target" >&2; exit 1 ;;
  esac
done
