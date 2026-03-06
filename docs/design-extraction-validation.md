# Design Extraction Validation

Generated from the current PDF-aware design-extraction flow.

## Corpus Baseline

- `pdf_text`: 109 (threshold `100`)
- `with_design_pages`: 134 (threshold `110`)
- `with_components`: 114 (threshold `80`)
- `with_layout`: 94 (threshold `85`)
- `with_equations`: 69 (threshold `40`)

## Category Baselines

| Category | Total | pdf_text | Design Pages | Components | Layout | Equations | Thresholds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Buck | 39 | 37 | 38 | 37 | 36 | 25 | pdf_text≥35, design_pages≥35, components≥35, layout≥33, equations≥18 |
| DAC | 1 | 1 | 1 | 1 | 0 | 0 | design_pages≥1, components≥1 |
| Interface | 8 | 3 | 8 | 7 | 5 | 4 | design_pages≥2, components≥1, layout≥1 |
| LDO | 41 | 39 | 39 | 37 | 30 | 27 | pdf_text≥35, design_pages≥35, components≥30, layout≥25, equations≥20 |
| OpAmp | 10 | 2 | 2 | 2 | 1 | 2 | design_pages≥1, layout≥1, equations≥1 |
| Switch | 15 | 6 | 10 | 6 | 4 | 3 | design_pages≥6, layout≥2, equations≥1 |

## Sample Devices

| MPN | Category | Source | Pages | Components | Layout | Equations | Quickstart |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| TPS62147 | Buck | pdf_text | 11 | 12 | 9 | 3 | `docs/design-extraction-samples/TPS62147.md` |
| LP5907 | LDO | pdf_text | 8 | 6 | 3 | 1 | `docs/design-extraction-samples/LP5907.md` |
| ADM7155 | LDO | pdf_text | 7 | 8 | 5 | 1 | `docs/design-extraction-samples/ADM7155.md` |
| AD8571/AD8572/AD8574 | OpAmp | pdf_text | 3 | 12 | 2 | 5 | `docs/design-extraction-samples/AD8571_AD8572_AD8574.md` |
| ADG706/ADG707 | Switch | pdf_text | 5 | 4 | 0 | 4 | `docs/design-extraction-samples/ADG706_ADG707.md` |

## Notes

- This is still a text-first extraction flow; it does not yet parse schematic figures as structured netlists.
- Coverage is strongest on regulators and power devices, then layout-heavy analog devices.
- Larger architecture changes such as a new OCR/Vision design-extraction stage should be discussed before implementation.
