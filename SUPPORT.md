# Support

Use the right channel so maintainers can respond efficiently and sensitive issues stay private.

## Which channel should I use?

### Support / usage questions
Use the normal project discussion or issue flow for:
- local setup questions
- how to run a script or validation command
- help understanding exported data or schema fields
- clarification about expected repository workflow

Before opening a support request, check:
- `README.md`
- `GUIDE.md`
- `CONTRIBUTING.md`

## Bug reports
Open a bug report when something is broken or regressed, for example:
- a documented command no longer works
- validation or regression checks fail unexpectedly
- generated outputs are wrong due to a reproducible repository bug
- CI or tooling behavior is inconsistent with the documented workflow

Use the bug template and include:
- the command you ran
- relevant file paths
- expected behavior
- actual behavior
- logs or error output

## Feature requests
Open a feature request when you want to propose:
- documentation or tooling improvements
- non-breaking workflow improvements
- new validation or extraction quality-of-life enhancements
- repository maintenance improvements

Use the feature template and describe:
- what you want
- why it helps
- scope and acceptance criteria

## Security issues
Do **not** open a public issue for:
- exposed API keys, tokens, cookies, or credentials
- exploitable vulnerabilities
- dependency or workflow issues with real security impact

Use the private reporting path described in `SECURITY.md`.
If a secret is involved, redact it and rotate it first when possible.

## Not sure?
Use this rule of thumb:
- broken behavior -> bug report
- new idea / improvement -> feature request
- sensitive exploit or secret exposure -> security report
- how-to / usage confusion -> support request
