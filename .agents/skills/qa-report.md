# Skill: QA report

1. List acceptance criteria (story) and scenarios (spec). One table row each.
2. For each row cite evidence: test name/path, or code location. None -> result `not verified`.
3. Collect findings with severity {blocker, major, minor}.
4. Verdict rule: pass = all rows evidenced + zero blocker/major. blocked = cannot verify critical rows. Else fail.
5. Always fill `Not verified`.
