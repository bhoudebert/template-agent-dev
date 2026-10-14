#!/bin/sh
# kit.sh <agentkit args...>  - run the kit's engine from a repository that has it installed.
# Prefers the `agentkit` release file on PATH (it carries the newest kit, so `update` works);
# falls back to this repository's own copy (enough for status, check, uninstall, reconcile).
if command -v agentkit >/dev/null 2>&1; then
  exec agentkit "$@"
fi
exec python3 "$(dirname "$0")/agentkit.py" "$@"
