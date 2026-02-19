# OpenDatasheet

AI-powered electronic component datasheet parameter extraction pipeline.

## Pipeline

- **v0.1** — Text mode: PyMuPDF text extraction → Gemini LLM → JSON
- **v0.2** — Vision mode: PyMuPDF page classification → Gemini Vision (page images) → JSON + cross-validation

## Results

- [AMS1117 Vision Extraction Result](docs/ams1117-vision-result.md) — Non-standard dual-row table benchmark

## Stack

- PyMuPDF (page classification + text extraction)
- Gemini 3 Flash (LLM / Vision extraction)
- Pydantic-style validation (L2 physics rules)
- Cross-validation (L3 PDF text vs extraction)
