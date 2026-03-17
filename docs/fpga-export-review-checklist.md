# FPGA Export Review Checklist

> Concrete review checklist for new or regenerated FPGA exports.

## Identity

- device name matches source material
- package name matches source material
- filename follows `{Device}_{Package}.json`

## Pin integrity

- `pins` count is plausible for the package
- every pin has physical identifier and name
- config pins are not misclassified as generic IO
- power and ground pins look complete

## Bank integrity

- `banks` exists
- bank count is plausible for the family and package
- IO bank records are not obviously empty when the package is IO-heavy

## Diff pair integrity

- `diff_pairs` references valid pins
- polarity assignment looks sane
- refclk pairs are separated from ordinary IO diff pairs where appropriate

## Lookup integrity

- `lookup.pin_to_name` resolves all physical pins
- `lookup.name_to_pin` does not silently collapse distinct names without review

## Capability and constraints

- high-speed packages expose source-backed capability blocks
- refclk-aware packages expose `constraint_blocks.refclk_requirements`
- package-specific constraints do not rely on family marketing claims alone

## Regression and validation

Run:

```bash
python3 scripts/validate_exports.py --summary
python3 test_regression.py -k fpga
```

If the parser changed materially:

```bash
python3 -m pytest -q
```

## Final sanity question

If a board architect used this export to plan:
- bank ownership
- refclk ownership
- diff-pair routing

would they be learning package truth, or only family-level approximation?
