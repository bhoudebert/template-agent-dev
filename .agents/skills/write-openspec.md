# Skill: write an OpenSpec change

1. Name the folder after the story id: `openspec/changes/US-123/`. Files start directly with `## ...`: NO frontmatter in any OpenSpec file.
2. `proposal.md`:
   ```
   ## Why
   ## What Changes
   ## Impact
   ```
3. `specs/<capability>/spec.md`:
   ```
   ## ADDED Requirements
   ### Requirement: <name>
   The system SHALL <behaviour>.

   #### Scenario: <name>
   - **WHEN** <trigger>
   - **THEN** <result>
   ```
4. `tasks.md`: `## 1. Group` then `- [ ] 1.1 task` items, ordered by dependency.
5. Self-check: each acceptance criterion -> scenario; every requirement has SHALL/MUST and a scenario.
