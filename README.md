# AgenticDev - vendor-neutral agentic SDLC template

Business -> spec -> architecture -> dev -> tests -> QA -> review -> release -> prod diagnosis,
one role-agent per stage, artifacts in git, humans at every gate.

Works with any LLM: Ollama/vLLM/llama.cpp/OpenAI via an OpenAI-compatible endpoint, or any CLI
(`claude -p`, `codex exec -`, `ollama run ...`) via `AGENT_CMD`. No Python dependencies.

Short commands: `mise tasks` (see GUIDE section 0).

**Start here: [docs/GUIDE.md](docs/GUIDE.md)** (setup, walkthrough, troubleshooting).

More: [docs/WORKFLOW.md](docs/WORKFLOW.md) (who does what, when), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/REFERENCE.md](docs/REFERENCE.md). Browse them as a website: `mise run site` (open http://localhost:8000).

## Layers
1. **Content** (portable markdown/yaml): `AGENTS.md`, `CONTEXT.md`, `.agents/{roles,skills,policies,templates,schemas,pipeline.yaml}`, `openspec/`, `docs/`.
2. **Core** (stdlib Python): `tools/agentrun.py` runner, `validate.py`, `trace_check.py`, `providers.py`.
3. **Adapters** (replaceable): `adapters/github/workflows`, tool pointers via `adapters/install.sh`.

## Try it

```sh
python -m unittest discover -s tools/tests
python tools/validate.py && python tools/trace_check.py     # worked example US-001 passes
python tools/agentrun.py list
python tools/agentrun.py run qa --id US-001 --dry-run       # inspect the exact prompt

# local model
export AGENT_PROVIDER=openai AGENT_BASE_URL=http://localhost:11434/v1 AGENT_MODEL=llama3.1
python tools/agentrun.py run qa --id US-001 --apply
# or any CLI agent
export AGENT_PROVIDER=cmd AGENT_CMD="claude -p"
```

## Use in a new project
1. Copy this repo's content layer + tools. Fill in `CONTEXT.md`.
2. `adapters/install.sh github tools` to wire CI and tool pointers.
3. Create `docs/stories/US-001.md` (raw request, `status: draft`) and walk the stages.

## Guarantees
- Output confined to each stage's `out` globs; path traversal rejected.
- Inputs wrapped as untrusted data; agents never merge or deploy.
- Validators/trace check are deterministic scripts, not LLM judgement.

## Not done yet
- Evals runner (`evals/README.md`), GitLab adapter, tracker (Jira/Linear) sync, observability connectors for `diagnose` (feed evidence by hand into `docs/incidents/INC-xxx.md` for now).
- GitHub workflows are untested against a real repo.
