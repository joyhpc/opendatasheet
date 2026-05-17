# Thermal And Parametric Derivation

Last audited from code: 2026-05-17.

Not every useful domain should start a fresh model/image pass. `thermal` and
`parametric` are intended to be low-cost derivation layers over already extracted
electrical facts.

## Thermal

`extractors/thermal.py` is currently wired as a derived domain. In
`pipeline_v2.py`, the orchestrator special-cases `thermal` and passes it the
electrical extraction result.

It extracts thermal-style facts such as:

- `theta_ja`
- `theta_jc`
- `theta_jb`
- `psi_jt`
- `power_dissipation`

The public exporter also derives a top-level `thermal` block from electrical and
absolute-maximum entries.

## Parametric

`extractors/parametric.py` is designed to derive selector-friendly summaries
from electrical extraction:

- voltage ranges
- current limits
- frequency limits
- operating-condition summaries
- category-specific key specs

Current caveat: as of this audit, `pipeline_v2.py` does not pass the electrical
result into `ParametricExtractor`. Since `ParametricExtractor.select_pages()`
returns an empty list, the orchestrator currently stores `{}` for that domain.

That is why current public exports have no non-empty `parametric` domain.

## Design Rule

Before adding a new image/model-backed domain, ask:

> Is the information genuinely missing, or is it already present in electrical
> data and only needs normalization?

Prefer derivation when:

- the source facts already exist in `electrical`
- the target domain is a stable lookup or selector projection
- a new model call would mostly duplicate existing extraction

Use a model-backed pass when:

- the needed facts are not in electrical tables
- the information depends on visual layout, diagrams, or context
- text extraction is demonstrably insufficient

## Validation

For derivation changes, run:

```bash
python scripts/validate_exports.py --summary
python -m pytest test_parametric_extraction.py -q
```

If local pytest plugin loading fails on Windows because of environment DLL
issues, disable plugin autoload:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest test_parametric_extraction.py -q
```
