# AMS1117 — Vision Extraction Result

> Historical sample artifact. This page is useful as an example of an older
> vision extraction report, but it is not a current architecture or coverage
> reference. For current repository state, read `docs/current-state.md`.

> Gemini 3 Flash Vision | Pipeline v0.2 | 2026-02-19

## Component Info

| Field | Value |
|-------|-------|
| MPN | AMS1117 |
| Manufacturer | Advanced Monolithic Systems, Inc. |
| Category | LDO |
| Description | 1A Low Dropout Voltage Regulator |

## Extraction Summary

| Metric | Value |
|--------|-------|
| Absolute Maximum Ratings | 8 params |
| Electrical Characteristics | 58 params |
| Pin Definitions | 0 |
| L2 Validation | 56/56 passed |
| L3 Cross-Validation | 98.7% value coverage |
| L3 Param Alignment | 65/66 verified |
| Extraction Time | 174.861s |

## Device Variant Coverage

| Device | 25C Params | Full Temp Params | Total |
|--------|------------|------------------|-------|
| (shared) | 1 | 3 | 4 |
| AMS1117 | 5 | 7 | 12 |
| AMS1117-1.5 | 3 | 3 | 6 |
| AMS1117-1.5/-1.8/-2.5/-2.85 | 0 | 1 | 1 |
| AMS1117-1.5/-1.8/-2.5/-2.85/-3.3/-5.0 | 0 | 3 | 3 |
| AMS1117-1.8 | 3 | 3 | 6 |
| AMS1117-2.5 | 3 | 3 | 6 |
| AMS1117-2.85 | 3 | 3 | 6 |
| AMS1117-3.3 | 3 | 4 | 7 |
| AMS1117-5.0 | 3 | 4 | 7 |

## Absolute Maximum Ratings

| Parameter | Symbol | Min | Typ | Max | Unit | Conditions |
|-----------|--------|-----|-----|-----|------|------------|
| Input Voltage | VIN | None | None | 15 | V |  |
| Operating Junction Temperature Control Section | TJ | -40 | None | 125 | °C |  |
| Operating Junction Temperature Power Transistor | TJ | -40 | None | 125 | °C |  |
| Storage temperature | TSTG | -65 | None | 150 | °C |  |
| Lead Temperature (25 sec) |  | None | None | 265 | °C | 25 sec |
| Thermal Resistance SO-8 package | φJA | None | None | 160 | °C/W |  |
| Thermal Resistance TO-252 package | φJA | None | None | 80 | °C/W |  |
| Thermal Resistance SOT-223 package | φJA | None | None | 90 | °C/W |  |

## Electrical Characteristics

### (shared)

| Parameter | Temp | Min | Typ | Max | Unit | Conditions |
|-----------|------|-----|-----|-----|------|------------|
| Long Term Stability | full | None | 0.3 | 1 | % | TA = 125°C, 1000Hrs |
| RMS Output Noise | 25C | None | 0.003 | None | % | TA = 25°C, 10Hz ≤ f ≤ 10kHz |
| Temperature Stability | full | None | 0.5 | None | % |  |
| Thermal Resistance Junction-to-Case | full | None | None | 15 | °C/W | All packages |

### AMS1117

| Parameter | Temp | Min | Typ | Max | Unit | Conditions |
|-----------|------|-----|-----|-----|------|------------|
| Adjust Pin Current | 25C | None | 55 | None | µA | IOUT = 10mA, 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Adjust Pin Current | full | None | None | 120 | µA | IOUT = 10mA, 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Adjust Pin Current Change | full | None | 0.2 | 5 | µA | IOUT = 10mA, 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Line Regulation | 25C | None | 0.015 | 0.2 | % | 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Line Regulation | full | None | 0.035 | 0.2 | % | 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Load Regulation | 25C | None | 0.1 | 0.3 | % | (VIN - VOUT) = 1.5V, 10mA ≤ IOUT ≤ 0.8A |
| Load Regulation | full | None | 0.2 | 0.4 | % | (VIN - VOUT) = 1.5V, 10mA ≤ IOUT ≤ 0.8A |
| Minimum Load Current | full | None | 5 | 10 | mA | (VIN - VOUT) = 1.5V |
| Reference Voltage | 25C | 1.232 | 1.25 | 1.268 | V | IOUT = 10 mA, 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Reference Voltage | full | 1.2125 | 1.25 | 1.2875 | V | IOUT = 10 mA, 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Ripple Rejection | full | 60 | 75 | None | dB | f = 120Hz, COUT = 22µF Tantalum, IOUT = 1A, (VIN - VOUT) = 3 |
| Thermal Regulation | 25C | None | 0.008 | 0.04 | %/W | TA = 25°C, 30ms pulse |

### AMS1117-1.5

| Parameter | Temp | Min | Typ | Max | Unit | Conditions |
|-----------|------|-----|-----|-----|------|------------|
| Line Regulation | 25C | None | 0.3 | 5 | mV | 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Line Regulation | full | None | 0.6 | 6 | mV | 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Load Regulation | 25C | None | 3 | 10 | mV | VIN = 3V, 0 ≤ IOUT ≤ 0.8A |
| Load Regulation | full | None | 6 | 20 | mV | VIN = 3V, 0 ≤ IOUT ≤ 0.8A |
| Output Voltage | 25C | 1.478 | 1.5 | 1.522 | V | VIN = 3V |
| Output Voltage | full | 1.455 | 1.5 | 1.545 | V | VIN = 3V |

### AMS1117-1.5/-1.8/-2.5/-2.85

| Parameter | Temp | Min | Typ | Max | Unit | Conditions |
|-----------|------|-----|-----|-----|------|------------|
| Ripple Rejection | full | 60 | 72 | None | dB | f = 120Hz, COUT = 22µF Tantalum, IOUT = 1A, VIN = 4.35V |

### AMS1117-1.5/-1.8/-2.5/-2.85/-3.3/-5.0

| Parameter | Temp | Min | Typ | Max | Unit | Conditions |
|-----------|------|-----|-----|-----|------|------------|
| Current Limit | full | 900 | 1100 | 1500 | mA | (VIN - VOUT) = 1.5V |
| Dropout Voltage | full | None | 1.1 | 1.3 | V | ΔVOUT, ΔVREF = 1%, IOUT = 0.8A |
| Quiescent Current | full | None | 5 | 11 | mA | (VIN - VOUT) = 1.5V |

### AMS1117-1.8

| Parameter | Temp | Min | Typ | Max | Unit | Conditions |
|-----------|------|-----|-----|-----|------|------------|
| Line Regulation | 25C | None | 0.3 | 5 | mV | 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Line Regulation | full | None | 0.6 | 6 | mV | 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Load Regulation | 25C | None | 3 | 10 | mV | VIN = 3.3V, 0 ≤ IOUT ≤ 0.8A |
| Load Regulation | full | None | 6 | 20 | mV | VIN = 3.3V, 0 ≤ IOUT ≤ 0.8A |
| Output Voltage | 25C | 1.773 | 1.8 | 1.827 | V | VIN = 3.3V |
| Output Voltage | full | 1.746 | 1.8 | 1.854 | V | VIN = 3.3V |

### AMS1117-2.5

| Parameter | Temp | Min | Typ | Max | Unit | Conditions |
|-----------|------|-----|-----|-----|------|------------|
| Line Regulation | 25C | None | 0.3 | 6 | mV | 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Line Regulation | full | None | 0.6 | 6 | mV | 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Load Regulation | 25C | None | 3 | 12 | mV | VIN = 5V, 0 ≤ IOUT ≤ 0.8A |
| Load Regulation | full | None | 6 | 20 | mV | VIN = 5V, 0 ≤ IOUT ≤ 0.8A |
| Output Voltage | 25C | 2.463 | 2.5 | 2.537 | V | VIN = 4V |
| Output Voltage | full | 2.425 | 2.5 | 2.575 | V | VIN = 4V |

### AMS1117-2.85

| Parameter | Temp | Min | Typ | Max | Unit | Conditions |
|-----------|------|-----|-----|-----|------|------------|
| Line Regulation | 25C | None | 0.3 | 6 | mV | 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Line Regulation | full | None | 0.6 | 6 | mV | 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Load Regulation | 25C | None | 3 | 12 | mV | VIN = 4.35V, 0 ≤ IOUT ≤ 0.8A |
| Load Regulation | full | None | 6 | 20 | mV | VIN = 4.35V, 0 ≤ IOUT ≤ 0.8A |
| Output Voltage | 25C | 2.808 | 2.85 | 2.892 | V | VIN = 4.35V |
| Output Voltage | full | 2.7645 | 2.85 | 2.9355 | V | VIN = 4.35V |

### AMS1117-3.3

| Parameter | Temp | Min | Typ | Max | Unit | Conditions |
|-----------|------|-----|-----|-----|------|------------|
| Line Regulation | 25C | None | 0.5 | 10 | mV | 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Line Regulation | full | None | 1.0 | 10 | mV | 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Load Regulation | 25C | None | 3 | 15 | mV | VIN = 4.75V, 0 ≤ IOUT ≤ 0.8A |
| Load Regulation | full | None | 7 | 25 | mV | VIN = 4.75V, 0 ≤ IOUT ≤ 0.8A |
| Output Voltage | 25C | 3.251 | 3.3 | 3.349 | V | VIN = 4.8V |
| Output Voltage | full | 3.201 | 3.3 | 3.399 | V | VIN = 4.8V |
| Ripple Rejection | full | 60 | 72 | None | dB | f = 120Hz, COUT = 22µF Tantalum, IOUT = 1A, VIN = 4.75V |

### AMS1117-5.0

| Parameter | Temp | Min | Typ | Max | Unit | Conditions |
|-----------|------|-----|-----|-----|------|------------|
| Line Regulation | 25C | None | 0.5 | 10 | mV | 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Line Regulation | full | None | 1.0 | 10 | mV | 1.5V ≤ (VIN - VOUT) ≤ 12V |
| Load Regulation | 25C | None | 5 | 20 | mV | VIN = 6.5V, 0 ≤ IOUT ≤ 0.8A |
| Load Regulation | full | None | 10 | 35 | mV | VIN = 6.5V, 0 ≤ IOUT ≤ 0.8A |
| Output Voltage | 25C | 4.925 | 5.0 | 5.075 | V | VIN = 6.5V |
| Output Voltage | full | 4.85 | 5.0 | 5.15 | V | VIN = 6.5V |
| Ripple Rejection | full | 60 | 68 | None | dB | f = 120Hz, COUT = 22µF Tantalum, IOUT = 1A, VIN = 6.5V |

## Text-only vs Vision Comparison

| Metric | Text v0.1 | Vision v0.2 |
|--------|-----------|-------------|
| EC Parameters | 21 | 58 |
| Device Variants | 1 | 10 |
| Temperature Coverage | 25C only | 25C + full |
| L2 Validation | 21/21 | 56/56 |
| L3 Cross-Validation | N/A | 98.7% |
| Extraction Time | 27s | 175s |

## Key Finding

The AMS1117 datasheet uses a **non-standard dual-row table format** where each parameter has two rows:
- **Bold row**: Full temperature range specs (-40C to 125C)
- **Normal row**: 25C specs

Text-only extraction (PyMuPDF to LLM) fails because the text extraction destroys the table structure,
causing min/typ/max values from different rows to interleave.

Vision extraction (page image to Gemini Vision) preserves the visual table structure and correctly
separates both temperature rows for all 7+ device variants.
