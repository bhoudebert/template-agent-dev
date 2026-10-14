# Skill: triage an incident

1. Scope: what is broken, since when, blast radius, severity (sev1 = outage/data loss).
2. Timeline: correlate first symptom with deploys, config, traffic, dependencies.
3. Hypotheses: 2-4, ranked; for each: evidence for/against, cheapest confirming check.
4. Mitigation first (rollback, flag, scale) - for a human to execute - then root-cause fix.
5. If a runbook exists, follow and cite it; if a new pattern, propose a runbook in docs/runbooks.
