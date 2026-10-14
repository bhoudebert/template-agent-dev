#!/bin/sh
# Run the project's own tests, whatever the stack.
#   1. `commands.test` in .agents/pipeline.yaml (monorepos, custom runners)
#   2. else auto-detect at the repository root: npm, pytest, go, cargo, mvn
#   3. else say so: nothing to run is not the same as "tests pass"
cd "$(dirname "$0")/.."
cmd=$(python3 tools/config.py command test 2>/dev/null)
if [ -n "$cmd" ]; then
  exec sh -c "$cmd"
fi
if   [ -f package.json ]; then exec npm test
elif [ -f pyproject.toml ] || [ -f pytest.ini ] || [ -f setup.cfg ]; then exec python3 -m pytest
elif [ -f go.mod ]; then exec go test ./...
elif [ -f Cargo.toml ]; then exec cargo test
elif [ -f pom.xml ]; then exec mvn -q test
elif [ -d tools/tests ]; then exec python3 -m unittest discover -s tools/tests   # the kit's own repository
fi
echo "no test command found at the repository root." >&2
echo "Set one in .agents/pipeline.yaml:" >&2
echo "  commands:" >&2
echo "    test: \"cargo test --manifest-path backend/Cargo.toml && npm --prefix ui test\"" >&2
exit 1
