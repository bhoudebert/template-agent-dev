#!/bin/sh
# Run the project's own tests, whatever the stack.
# Falls back to the template's tool tests when no project test config is found.
cd "$(dirname "$0")/.."
if   [ -f package.json ]; then exec npm test
elif [ -f pyproject.toml ] || [ -f pytest.ini ] || [ -f setup.cfg ]; then exec python3 -m pytest
elif [ -f go.mod ]; then exec go test ./...
elif [ -f Cargo.toml ]; then exec cargo test
elif [ -f pom.xml ]; then exec mvn -q test
else exec python3 -m unittest discover -s tools/tests
fi
