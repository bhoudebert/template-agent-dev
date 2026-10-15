# AgenticDev

An agent at every step, a human at every gate. A vendor-neutral workflow for taking a change from a rough
request to a released version, with the artifacts in git and nothing reaching `main` except through a pull request.

```
request -> story -> spec -> design -> implement -> test -> QA -> review -> release -> (prod) diagnose
```

- **Any model**: a local Ollama, any OpenAI-compatible API, or a CLI you already use. Or let an assistant
  (Claude Code, Codex, Copilot) drive the same steps from its prompt.
- **Deterministic guard rails**: schemas, traceability, an evidence floor and a no-assistant-names rule are
  checked by scripts, not by a model.
- **Standard-library Python, no dependencies.** Short commands through [mise](https://mise.jdx.dev).

## Install it in your repository

```sh
mkdir -p ~/.local/bin
os=$(uname -s); arch=$(uname -m)
case "$os" in Darwin) os=apple-darwin;; *) os=unknown-linux-gnu;; esac
case "$arch" in arm64|aarch64) arch=aarch64;; *) arch=x86_64;; esac
curl -fsSL "https://github.com/bhoudebert/template-agent-dev/releases/latest/download/agentkit-$arch-$os.tar.gz" \
  | tar -xz -C ~/.local/bin
cd my-repo
agentkit install --plan      # see what it would do
agentkit install             # a branch and one commit; nothing is pushed; review it as a PR
```

`agentkit` manages the kit (install, update, status, todo); `mise run` does the daily work ([which one when](docs/REFERENCE.md#three-ways-to-run-things)).

Full steps, first-run checklist, updates, conflicts and removal: **[docs/INSTALL.md](docs/INSTALL.md)**.

### How updates reach you (read this once)

Two things exist: the **program** (`agentkit`, one file on your PATH, installed from a GitHub release, holding a
frozen snapshot of the kit) and the **copy in your repo** (`tools/`, `.agents/`, ... plus `.agentkit/lock.json`).
Nothing updates itself:

1. `mise upgrade agentkit` gets a newer program (`agentkit --version` shows which).
2. `agentkit update`, in each repo, copies its snapshot in on a branch as one commit; you review and merge the PR.

Until then the old program and files keep working; `agentkit status` only compares, it downloads nothing.
Details and the "stuck" table: **[The mental model](docs/INSTALL.md#the-mental-model-read-this-once)**.

## Learn it

| Read | For |
|---|---|
| [docs/INSTALL.md](docs/INSTALL.md) | install, update, uninstall |
| [docs/TUTORIAL.md](docs/TUTORIAL.md) | one Node.js story end to end, every manual and automated step |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | who does what, and when; bugs and emergencies |
| [docs/GUIDE.md](docs/GUIDE.md) | day-to-day use |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | how it works and why |
| [docs/REFERENCE.md](docs/REFERENCE.md) | tasks, settings, schemas, exit codes |

Browse them as a website: `mise run site` (http://localhost:8000).

## Work on the kit itself

```sh
mise run check            # validators + the kit's tests (python -m unittest discover -s tools/tests)
mise run kit:install ../my-repo --plan
```

Every change goes through a branch and a PR (`mise run ship`).

## Honest status

- Not built: an evals runner (`evals/README.md`), a GitLab adapter, tracker sync (ids can adopt a tracker key,
  but there is no import), observability connectors for `diagnose` (paste evidence by hand).
- The release asset and its mise `github:` install are unverified until the first tagged release.
- The agent reviewer and LLM reconcile are advice: their output is always a diff you review.
