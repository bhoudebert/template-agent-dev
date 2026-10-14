# Evals (next step)

Goal: detect silent regressions when a model, prompt or role changes.

Planned case format: `evals/cases/<stage>/<name>/{input/, expect.json}` where `expect.json` lists
`must_validate: true`, `must_contain: [...]`, `must_not_write: [...]`.
Run each case through `tools/agentrun.py` against a sandbox copy and assert on validators.
Not implemented yet: add a runner when the first real role prompt is tuned.
