# Agent Guidance

Use the repository docs as a routed knowledge base, not a bulk context source.

## Default Navigation

Start with exactly one of these:
- `README.md`
- `GUIDE.md`
- `docs/index.md`
- `docs/hardware-engineer-index.md`

Only open deeper docs after you know the task category.

## Context Discipline

Do not scan the whole `docs/` tree by default.

Prefer this pattern:
1. identify the task type
2. open the matching index page
3. open at most 1 to 3 directly relevant docs
4. return to code, data, or commands

## Tool-Use Rule

When calling tools for a coding or validation task:
- prefer source files, scripts, tests, schema, and the smallest relevant doc
- do not read broad documentation sets unless the task is explicitly documentation-oriented
- do not open `docs/hardware-engineering/` recursively

## Remote Sync Rule

After completing a major optimization:
- run the relevant local validation first
- proactively sync the working branch to the remote unless the user explicitly asks to hold changes or credentials/permissions block the push

## Suggested Entry Points

For repository workflow:
- `README.md`
- `GUIDE.md`
- `docs/first-30-minutes.md`
- `docs/local-setup-playbook.md`

For export/schema/integration:
- `docs/index.md`
- `docs/sch-review-integration.md`
- `docs/normal-ic-export-field-guide.md`
- `docs/fpga-export-field-guide.md`

For hardware review tasks:
- `docs/hardware-engineer-index.md`

For FPGA parser tasks:
- `docs/fpga-pinout-parser-overview.md`

## Avoid

- loading all markdown files into context
- opening all docs in a category “just in case”
- using documentation as a substitute for reading the actual script or schema being changed

## Priority Rule

If code, schema, checked-in data, and docs disagree:
- trust the code and schema first
- use docs for intent, workflow, and review framing
