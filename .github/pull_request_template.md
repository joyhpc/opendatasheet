## Before You Submit

- For setup, validation steps, and contribution rules, see `CONTRIBUTING.md`.
- For general usage or triage questions, start with `SUPPORT.md`.
- For secrets exposure or exploitable vulnerabilities, stop and follow `SECURITY.md` instead of opening a public PR.

## Summary

- What changed?
- Why is this needed?

## Scope

- [ ] Source code
- [ ] Generated data
- [ ] Docs / metadata only
- [ ] CI / tooling

## Validation

- [ ] `./scripts/run_checks.sh`
- [ ] If `docs/hardware-engineering/` changed: `python3 scripts/check_markdown_links.py docs/hardware-engineering && python3 scripts/check_hardware_doc_structure.py`
- [ ] `python3 scripts/validate_exports.py --summary`
- [ ] `python3 test_regression.py`
- [ ] `python3 -m pytest -q`
- [ ] Not run (explain below)

## Notes

- Risks / follow-ups:
- Related issues / context:
