# OpenDatasheet

AI-powered electronic component datasheet parameter extraction pipeline.
PDF datasheets → structured JSON for schematic review DRC engines.

## 📖 [Reading Guide](GUIDE.md) — Start here

## Quick Links

- [Extraction Methodology](docs/extraction-methodology.md) — How the Vision + Text hybrid pipeline works
- [Schematic Review Integration](docs/sch-review-integration.md) — Data structures, examples, and Python code for consumers
- [Schema](schemas/sch-review-device.schema.json) — `sch-review-device/1.0` JSON Schema
- [Exported Data](data/sch_review_export/) — 85 device files ready for consumption

## Pipeline

```
PDF → L0 Page Classification (PyMuPDF + regex)
    → L1a Vision Extraction (Gemini Flash, page images)
    → L1b Pin Extraction (Gemini Flash, page images)
    → L2 Physics Validation (unit/range/consistency checks)
    → L3 Cross-Validation (extracted values vs PDF raw text, 95-100% coverage)
```

## Coverage

| Type | Count | Examples |
|------|-------|---------|
| Normal IC | 54 | LDO, Buck, OpAmp, Switch, ADC/DAC, Interface, SerDes |
| FPGA | 31 | Xilinx UltraScale+, Gowin GW5AT/GW5AR, Lattice ECP5/CrossLink-NX |
| **Total** | **85** | Batch processing 346 PDFs (in progress) |

## Stack

- **PyMuPDF** — PDF rendering + text extraction
- **Gemini 3 Flash** — Multimodal Vision extraction (page images → structured JSON)
- **Pydantic-style validation** — L2 physics rules
- **Cross-validation** — L3 PDF raw text vs extracted values
