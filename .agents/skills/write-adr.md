# Skill: write an ADR

- Next id = highest `ADR-NNNN` in docs/decisions + 1 (4 digits). File: `docs/decisions/ADR-NNNN-kebab-title.md`.
- Frontmatter: id, type: adr, title, status: proposed, story, date.
- Context: forces and constraints, not history.
- Options: >= 2, each with honest cons. "Do nothing" counts if viable.
- Decision: one sentence, then reasons tied to the constraints.
- Consequences: positive, negative, follow-ups. Supersede old ADRs by setting their status to `superseded` in a separate edit note.
