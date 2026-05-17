# Gemini API Operations

Last audited from code: 2026-05-17.

This document applies only to the model-backed extraction path implemented by
`pipeline_v2.py` and model-backed extractors. It does not describe the whole
repository workflow. Current public exports are a mixed corpus that also
includes deterministic FPGA parser outputs and manual/curated profiles.

## When Gemini Is In The Path

Gemini is used when:

- `pipeline_v2.py` runs on a PDF and selected extractor pages are rendered to
  PNG
- a model-backed extractor calls `extractors/gemini_json.py`
- `scripts/extract_design_guide_pdf.py` runs with credentials and selected pages

Gemini is not used for:

- `scripts/export_for_sch_review.py`
- `scripts/validate_exports.py`
- FPGA vendor pinout parsing
- raw-source manifest generation
- most downstream export consumption

## Hard Requirements

- `GEMINI_API_KEY` must be set before running model-backed extraction.
- The pipeline should fail fast if the key is absent.
- The repository should not contain or rely on a hardcoded fallback key.
- Key checks should be separated from full PDF extraction runs.

## Failure Classes

### Permission Failure

Typical signals:

- `403 PERMISSION_DENIED`
- suspended consumer/project
- invalid or unauthorized key

Meaning:

- not a prompt issue
- not a page-classification issue
- not a PDF text extraction issue

Action:

- stop the batch
- run a minimal key probe
- replace or fix credentials before retrying

### Network Hang Or Long Read

Typical signals:

- a call blocks in `httpx` or TLS socket read
- no response headers arrive for a long time
- one domain consistently takes much longer than expected

Meaning:

- upstream did not respond in time, or
- routing selected too many or wrong pages, or
- an expensive domain is being run on the wrong component class

Action:

- inspect the active extractor and selected page list
- reduce page/domain scope before increasing timeout
- avoid repeating a large batch until the selector is understood

### Structured Extraction Failure

Typical signals:

- API call succeeds
- returned text is not valid JSON
- required keys are missing
- parsed JSON is low quality

Action:

- inspect prompt identity and prompt hash
- inspect selected pages
- check whether the domain belongs on that component class
- add focused tests or fixtures if the failure class should not recur

## Safe Probe Pattern

Before launching a large model-backed batch, use a minimal probe:

```bash
python - <<'PY'
from google import genai
import os

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
resp = client.models.generate_content(model="gemini-2.5-flash", contents="ping")
print(bool(resp))
PY
```

The probe model can change over time; keep the probe cheap and deterministic.

## Operational Rules

- Record whether a generated file is model-backed, manual, or parser-derived.
- Preserve model traces when using current trace-capable extraction code.
- Do not describe manual profiles as Gemini output.
- Do not route simple component classes through expensive domains without a
  domain-specific reason.
- Do not debug export schema failures by changing prompts; first inspect
  `scripts/export_for_sch_review.py` and the schema.

## Related Docs

- [Current State](current-state.md)
- [Extraction Methodology](extraction-methodology.md)
- [Architecture](architecture.md)
- [Domain Cost Control](domain-cost-control.md)
