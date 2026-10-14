---
id: US-000
type: story
kind: bug
title: Short description of the failure
status: enriched
owner: product-owner
# keep skip/skip_reason if the input has them
---

## Symptom
What happens, where, since when, how often. Quote the error or the wrong output.

## Expected behaviour
What should happen, citing the story, spec requirement or ADR that says so (find it in docs/INDEX.md).
If nothing covers it, say "not specified": a spec update is then part of the fix.

## Reproduction
1. Steps, data and environment that reproduce it.

## Acceptance criteria
- Given <state>, when <action>, then <the failure no longer occurs>.
- A non-regression test fails before the fix and passes after it.

## Out of scope
- What this fix deliberately does not change.

## Open questions
- Anything unknown about the cause or the expected behaviour (or "None").
