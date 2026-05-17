# Extraction Methodology

Last audited from code and checked-in data: 2026-05-17.

This document describes implemented extraction paths. It does not claim that all
current checked-in data was produced by one path.

## Current Reality

OpenDatasheet has multiple ingestion paths:

1. model-backed PDF extraction implemented by `pipeline_v2.py`
2. text/derived extractors that do not call a model
3. manual or curated profile JSON
4. deterministic FPGA pinout parsers

The public export corpus is generated from checked-in intermediate data and FPGA
pinout JSON. It should not be summarized as a pure Gemini Vision corpus.

## Model-Backed PDF Path

`pipeline_v2.py` implements this flow:

```text
PDF
  -> L0 page classification with PyMuPDF text and regex
  -> registered extractor page selection
  -> selected pages rendered to PNG
  -> model-backed extractor calls through extractors/gemini_json.py
  -> validation and cross-validation
  -> data/extracted_v2/*.json
```

This path requires `GEMINI_API_KEY`.

### L0 Page Classification

`classify_pages()` reads PDF page text and assigns categories such as:

- `cover`
- `electrical`
- `pin`
- `ordering`
- `application`
- `fpga_supply`
- `image_only`
- `other`

The point of L0 is routing and cost control: extractors should only render and
send relevant pages when they actually have pages to inspect.

### Model-Backed Domains

These extractors call the shared Gemini JSON helper when selected pages exist:

- `electrical`
- `pin`
- `register`
- `timing`
- `power_sequence`
- `protocol`
- `package`
- `design_guide` for its vision portion

The shared helper is `call_gemini_json_response()` in
`extractors/gemini_json.py`. It builds a prompt plus PNG image parts, calls
`client.models.generate_content(...)`, parses JSON, normalizes key aliases, and
attaches non-serialized model trace metadata to the returned `TraceableDict`.

### Text And Derived Domains

Not every extractor should start a new image/model pass.

- `design_context` reads PDF text directly and uses `design_info_utils.py`.
- `thermal` post-processes the electrical extraction result.
- `parametric` is intended to post-process electrical extraction into
  comparison-oriented specs, but the current orchestrator does not pass the
  electrical result into it.

### Validation

The model-backed normal-IC path includes:

- range/unit/monotonicity-style checks inside domain validators
- PDF-text numeric cross-validation through `cross_validate()`
- physics checks for selected electrical relationships
- pin validation for enum values and package mappings

These validations are useful, but they do not replace human review for new
device families or ambiguous datasheets.

## Checked-In Intermediate Data

Current top-level `data/extracted_v2/*.json` files are mostly legacy flat
extraction outputs:

- 179 files excluding `_summary.json`
- 175 have `model=gemini-3-flash-preview` and `mode=vision`
- 4 have `model=manual_profile` and `mode=manual`
- 6 have a top-level `domains` block
- 0 have non-empty `domain_traces`
- no current `_audit/*.model_trace.json` sidecar directory is present

That means older files may contain model labels, but they are not uniformly
audit-traceable with current sidecar machinery.

## Manual And Curated Profiles

Some inputs are intentionally curated profiles. Current examples include
automotive video SerDes-related files marked `manual_profile`.

Manual profiles are valid inputs when they are explicit. They should not be
described as Gemini output, and future manual additions should record source
basis clearly in the JSON or adjacent documentation.

## FPGA Pinout Path

FPGA package data is a separate structural parsing problem. It does not follow
the normal-IC vision table path.

```text
vendor pinout source
  -> scripts/parse_pinout.py or vendor-specific parser
  -> data/extracted_v2/fpga/pinout/*.json
  -> scripts/export_for_sch_review.py
  -> data/sch_review_export/*_{package}.json
```

The parser output is expected to contain:

- physical pins
- banks
- differential pairs
- lookup maps
- power/config/ground/special classification
- package and source traceability where available

## Current Domain Coverage

Do not infer coverage from extractor existence. Current public exports have
non-empty data for some domains and none for others.

See [Current State](current-state.md) for the current coverage table.

## When To Use This Path

Use model-backed extraction when:

- a normal IC datasheet has useful tables that are not already represented
- visual table layout is important
- the source PDF is present and valid
- model credentials are available
- provenance can be preserved

Use deterministic parsing or manual curation when:

- the source format is structured, such as FPGA pinout workbooks
- vendor format rules are stable enough to encode
- a profile needs human interpretation and should be labeled as manual

## Known Issues

- `parametric` is registered but not wired correctly into `pipeline_v2.py`.
- Current raw sources are partial relative to checked-in exports.
- Historical model-backed outputs lack current audit sidecars.
- Some old docs overstate Vision coverage. Prefer this document and
  [Current State](current-state.md).
