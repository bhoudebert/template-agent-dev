---
id: ADR-0001
type: adr
title: Store reset tokens hashed with SHA-256
status: proposed
story: US-001
date: 2026-10-14
---

## Context
Reset tokens grant account takeover if leaked from the database. Tokens are high-entropy and short-lived.

## Options considered
1. **Plaintext tokens** - simple; a DB leak exposes live tokens.
2. **SHA-256 of a 256-bit random token** - cheap, safe given entropy; lookup by hash.
3. **Slow password hash (bcrypt)** - unnecessary cost for high-entropy tokens, complicates lookup.

## Decision
Store SHA-256 hashes of 256-bit random tokens; compare in constant time.

## Consequences
- Positive: DB leak does not expose usable tokens; indexed lookup.
- Negative: tokens cannot be re-sent; a new one is issued instead.
- Follow-ups: document in runbook how to invalidate all tokens.
