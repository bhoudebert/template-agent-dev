#!/bin/sh
# stage.sh STAGE ID [dry] [plan]   - thin wrapper used by mise tasks.
#   default: --apply   dry: print prompt only   plan: call LLM, write nothing
set -e
cd "$(dirname "$0")/.."
stage="$1"; id="$2"
[ -n "$stage" ] && [ -n "$id" ] || { echo "usage: stage.sh STAGE ID [dry] [plan]" >&2; exit 64; }
if [ "$3" = "true" ]; then mode="--dry-run"
elif [ "$4" = "true" ]; then mode=""
else mode="--apply"; fi
exec python3 tools/agentrun.py run "$stage" --id "$id" $mode
