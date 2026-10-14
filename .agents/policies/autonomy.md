# Policy: autonomy

Agents propose; humans dispose.
- Level 0 (default): agents write artifacts to a branch/PR. A human approves the gate in pipeline.yaml.
- Agents never merge, deploy, change infra, rotate secrets or touch production.
- Raising autonomy (e.g. auto-merge docs-only changes) requires an ADR and passing evals.
