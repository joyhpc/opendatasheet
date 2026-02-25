# OpenDatasheet — Reading Guide

> AI-powered extraction pipeline: PDF datasheets → structured JSON for schematic review DRC

## Start Here

### 1. [Extraction Methodology](docs/extraction-methodology.md)
How the pipeline works: Vision + Text hybrid approach, why we render pages as images instead of parsing text, and how cross-validation catches errors.

### 2. [Schematic Review Integration](docs/sch-review-integration.md)
**The most important file for downstream consumers.** Complete data structure reference, JSON examples for both normal IC and FPGA, Python code snippets for every use case (pin lookup, Vout calculation, voltage limit check, FPGA bank/diff-pair/config DRC).

### 3. [Schema Definition](schemas/sch-review-device.schema.json)
Formal JSON Schema (`sch-review-device/1.0`). Two types: `normal_ic` (packages → pins + electrical params) and `fpga` (pins + banks + diff pairs + DRC rules + power rails).

## Data

### 4. [Exported Device Data](data/sch_review_export/) — 85 files (54 IC + 31 FPGA)
Ready-to-consume JSON files conforming to the schema above. One file per device (IC) or device+package (FPGA).

Example files to look at:
- [`LM5060.json`](data/sch_review_export/LM5060.json) — TI hot-swap controller, 10-pin, full electrical params + DRC hints
- [`TP2860.json`](data/sch_review_export/TP2860.json) — Techpoint video decoder, 40-pin QFN
- [`XCKU3P_FFVB676.json`](data/sch_review_export/XCKU3P_FFVB676.json) — Xilinx UltraScale+ FPGA, 676 pins, banks, diff pairs, DRC rules
- [`GW5AT-60_PG484A.json`](data/sch_review_export/GW5AT-60_PG484A.json) — Gowin FPGA with DC characteristics

### 5. [Raw Extraction Data](data/extracted_v2/) — 84+ files (growing)
Full pipeline output including page classification, cross-validation scores, timing, and physics validation. More detailed than sch_review_export but not schema-normalized.

## Design Docs

### 6. [Design Document](docs/design-document.md)
Original pipeline architecture and design decisions.

### 7. Technical Deep-Dives
- [Q1: Negative Value Validation](docs/Q1-negative-value-validation.md) — Dual-rail inference for ALGEBRAIC vs MAGNITUDE notation
- [Q2: Negative Text Matching](docs/Q2-negative-text-matching.md) — Unicode minus variant handling in cross-validation
- [Q3: Pin Schema Design](docs/Q3-pin-schema-design.md) — Logical pin model with multi-package mapping
- [Q4: FPGA DRC Data Loading Strategy](docs/Q4-fpga-drc-data-loading-strategy.md) — Code-graph base + LLM expert system architecture

## Code

| File | Purpose |
|------|---------|
| [`pipeline_v2.py`](pipeline_v2.py) | Core extraction pipeline (L0→L1a→L1b→L2→L3) |
| [`batch_all.py`](batch_all.py) | Batch processor for full IC library |
| [`scripts/export_for_sch_review.py`](scripts/export_for_sch_review.py) | Convert extracted_v2 → sch_review_export |
| [`scripts/parse_fpga_pinout.py`](scripts/parse_fpga_pinout.py) | AMD/Xilinx FPGA pinout parser |
| [`scripts/parse_gowin_pinout.py`](scripts/parse_gowin_pinout.py) | Gowin FPGA pinout parser |
| [`scripts/parse_lattice_pinout.py`](scripts/parse_lattice_pinout.py) | Lattice FPGA pinout parser |

## What This Data Can Do (for Schematic Review)

✅ **Pin function verification** — Check if pin connections match datasheet definitions
✅ **Voltage limit checking** — Compare net voltages against absolute maximum ratings
✅ **FB divider Vout calculation** — Use Vref from drc_hints to back-calculate output voltage
✅ **Unused pin treatment** — Verify floating/pull-up/pull-down per datasheet recommendation
✅ **FPGA power integrity** — All power/ground pins must be connected
✅ **FPGA config pin check** — Mandatory configuration pins must be wired correctly
✅ **FPGA bank VCCO consistency** — IO standards in same bank must share compatible VCCO
✅ **FPGA differential pair integrity** — Both P and N must be used together

## What's NOT Yet Extracted

❌ Register maps (pages identified but not parsed)
❌ Timing parameters (setup/hold/propagation delay)
❌ Application circuits / reference designs
❌ Thermal resistance (θJA/θJC)
❌ Recommended external component values (e.g., decoupling caps)

## Status

- **Batch processing**: 309 PDFs in progress (~34/309 done, ~6.5h remaining)
- **Total PDF library**: 346 datasheets
- **API**: Gemini 2.0 Flash (vision), well within rate limits
