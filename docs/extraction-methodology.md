# Extraction Methodology — Vision + Text Hybrid Pipeline

## Problem: Non-Standard Tables in PDF Datasheets

Electronic component datasheets are notoriously inconsistent:
- **Merged cells** spanning multiple rows/columns
- **Dual-row formats** (25°C specs + full temp range on separate rows)
- **Multi-variant tables** (multiple device models in one table)
- **Non-standard layouts** (Chinese/Japanese datasheets, small vendors)
- **PyMuPDF text extraction** produces garbled column alignment for complex tables

Pure text-based parsing fails on ~30-40% of real-world datasheets due to column misalignment.

## Solution: Vision-First Extraction

Instead of parsing extracted text, we **render PDF pages as images** and send them to a multimodal LLM (Gemini Vision) that "sees" the table layout visually.

### Pipeline Architecture

```
PDF ──→ L0: Page Classification (PyMuPDF text + regex)
          │
          ├─ electrical pages ──→ L1a: Vision Extraction (Gemini Vision)
          ├─ pin/cover pages  ──→ L1b: Pin Extraction (Gemini Vision)
          └─ other pages      ──→ skipped
          │
          ├──→ L2: Physics Validation (Pydantic rules)
          └──→ L3: Cross-Validation (extracted values vs PDF raw text)
```

### L0: Page Classification

PyMuPDF extracts raw text from each page. Regex patterns classify pages into categories:

| Category | Patterns | Action |
|----------|----------|--------|
| `electrical` | `absolute maximum`, `electrical characteristics`, `dc characteristics` | → Vision extraction |
| `pin` | `pin description`, `pin configuration`, `pin-out` | → Pin extraction |
| `cover` | First page, product summary | → Vision extraction (component info) |
| `ordering` | `ordering information`, `package marking` | → Vision extraction (package info) |
| `other` | Everything else (application notes, register maps, etc.) | → Skipped |

This pre-filtering reduces Vision API calls by ~70% (only 5-15 pages out of 30-400+ are sent to Vision).

### L1a: Vision Extraction (Electrical Parameters)

1. **Render** classified pages to PNG at 150 DPI using PyMuPDF
2. **Send** all page images in a single Gemini Vision call with a structured prompt
3. **Parse** the JSON response into `absolute_maximum_ratings` + `electrical_characteristics`

The prompt explicitly instructs the model to handle:
- Dual-row format (25°C + full temp range as separate entries)
- Multi-variant tables (extract per-device parameters)
- Merged cells and non-standard layouts
- Null values for unspecified min/typ/max

### L1b: Pin Extraction

Same Vision approach, but with a specialized prompt for pin definitions:
- Logical pin name, direction (`INPUT`/`OUTPUT`/`BIDIRECTIONAL`/`POWER_IN`/etc.)
- Signal type (`POWER`/`DIGITAL`/`ANALOG`)
- Per-package physical pin mapping
- Unused pin treatment (`PULL_UP`/`PULL_DOWN`/`GND`/`FLOAT`/`NC`)

### L2: Physics Validation

Automated sanity checks on extracted values:
- **Dual-rail inference**: Detects ALGEBRAIC vs MAGNITUDE notation for negative values
- **Unit validation**: Flags suspicious units (e.g., `μVPP/V`)
- **Range checks**: min ≤ typ ≤ max (accounting for negative/magnitude conventions)
- **Cross-parameter consistency**: e.g., operating voltage must be within absolute maximum

### L3: Cross-Validation

Extracts ALL numeric values from the PDF raw text, then checks if each extracted parameter value exists in the original PDF:
- Handles Unicode minus variants (`−`, `–`, `—`, `‐`)
- Handles scientific notation with spaces
- Reports `value_coverage_pct` (typically 95-100%)

## Model Choice

**`gemini-3-flash-preview`** via Google GenAI SDK (multimodal)

Why Flash over Pro:
- **Cost**: ~10x cheaper ($0.10/1M input vs $1.25/1M)
- **Speed**: ~2x faster per call
- **Accuracy**: Sufficient for structured table extraction (95-100% cross-validation)
- **Rate limits**: 15 RPM free tier handles our ~2 calls/min batch rate

## Performance

| Metric | Value |
|--------|-------|
| Processing speed | ~1.5 min/file (including rendering + API + validation) |
| Cross-validation coverage | 95-100% typical |
| Vision extraction success rate | ~85% first attempt, ~95% with retry |
| API calls per file | 2-3 (L1a + L1b + occasional retry) |

## Limitations

1. **Register maps**: Pages are classified but not extracted (future work)
2. **Timing parameters**: Setup/hold/propagation delay not separately categorized
3. **Application circuits**: Not structurally extracted
4. **Thermal resistance**: θJA/θJC not separately classified
5. **Memory**: Large PDFs (400+ pages) consume significant RAM during rendering
6. **Occasional unit errors**: Non-standard units may be misread (caught by L2 validation)
