# Policy: gates

Every stage ends at a gate named in `.agents/pipeline.yaml`.
- `human:<role>` = a named person approves the PR for that stage.
- `ci` = automated checks must pass.
- Status moves forward only by editing story frontmatter in a reviewed PR.
- Failed check -> fix and rerun the stage; do not edit validators to pass.
