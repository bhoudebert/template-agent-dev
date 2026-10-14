## Why
Users locked out of their account currently need support. Self-service reset removes that cost (US-001).

## What Changes
- Add request-reset and confirm-reset capability with single-use, expiring tokens.
- Add rate limiting on reset requests.

## Impact
- New capability `password-reset`; touches auth and email sending.
- Risk: account enumeration via response differences (mitigated by identical responses).
