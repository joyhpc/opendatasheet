# OpenDatasheet To Schematic Review Integration

Last audited from code and checked-in data: 2026-05-17.

This document describes how downstream schematic-review or DRC tools should
consume `data/sch_review_export/`.

## Current Contract

| Item | Current value |
|------|---------------|
| Export directory | `data/sch_review_export/` |
| Public export files | 255 |
| Normal IC exports | 172 |
| FPGA exports | 83 |
| Current export schema | `device-knowledge/2.0` |
| Validator | `python scripts/validate_exports.py --summary` |

All current public exports validate as `device-knowledge/2.0`.

The schema still accepts older `sch-review-device/1.0` and
`sch-review-device/1.1` payloads for compatibility, but new checked-in public
exports should be treated as v2.

## File Naming

```text
data/sch_review_export/
  {safe_mpn}.json              # normal IC
  {device}_{package}.json      # FPGA package export
  _manifest.json               # export index
  _fpga_catalog.json           # FPGA navigation catalog
```

`safe_mpn` is produced by replacing characters outside `[a-zA-Z0-9_-]` with
`_`.

## Normal IC Shape

Normal IC exports keep flat compatibility fields and a v2 `domains` block.

```json
{
  "_schema": "device-knowledge/2.0",
  "_type": "normal_ic",
  "_layers": ["L0_skeleton", "L1_electrical"],
  "mpn": "AMS1117",
  "manufacturer": "Advanced Monolithic Systems",
  "category": "LDO",
  "description": "1A low dropout voltage regulator",
  "packages": {
    "SOT-223": {
      "pin_count": 4,
      "pins": {
        "1": {
          "name": "ADJ/GND",
          "direction": "INPUT",
          "signal_type": "ANALOG",
          "description": "Adjust or ground pin",
          "unused_treatment": null
        }
      }
    }
  },
  "absolute_maximum_ratings": {},
  "electrical_parameters": {},
  "drc_hints": {},
  "thermal": {},
  "domains": {
    "pin": {
      "packages": {}
    },
    "electrical": {
      "absolute_maximum_ratings": {},
      "electrical_parameters": {},
      "drc_hints": {}
    }
  }
}
```

For new consumers, prefer `domains` where available. Keep fallback reads for the
flat fields because downstream code and historical artifacts still use them.

## FPGA Shape

FPGA exports are package-specific.

```json
{
  "_schema": "device-knowledge/2.0",
  "_type": "fpga",
  "mpn": "XCKU3P",
  "manufacturer": "AMD/Xilinx",
  "category": "FPGA",
  "package": "FFVB676",
  "supply_specs": {},
  "io_standard_specs": {},
  "power_rails": {},
  "banks": {},
  "diff_pairs": [],
  "drc_rules": {},
  "pins": [],
  "lookup": {
    "by_pin": {},
    "by_name": {}
  },
  "summary": {},
  "domains": {
    "pin": {
      "pins": [],
      "banks": {},
      "diff_pairs": [],
      "lookup": {}
    }
  }
}
```

FPGA consumers should load by both device and package. Package choice changes
physical pins, banks, and differential pairs.

## Robust Loader

```python
import json
import re
from pathlib import Path

EXPORT_DIR = Path("data/sch_review_export")


def safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", value)


def load_device(mpn: str, package: str | None = None) -> dict | None:
    if package:
        candidates = [
            EXPORT_DIR / f"{safe_name(mpn)}_{safe_name(package)}.json",
            EXPORT_DIR / f"{mpn}_{package}.json",
        ]
    else:
        candidates = [
            EXPORT_DIR / f"{safe_name(mpn)}.json",
            EXPORT_DIR / f"{mpn}.json",
        ]

    for path in candidates:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None
```

## Compatibility Accessors

Downstream code should tolerate both flat and domain shapes.

```python
def pin_domain(device: dict) -> dict:
    return (device.get("domains") or {}).get("pin") or {}


def electrical_domain(device: dict) -> dict:
    return (device.get("domains") or {}).get("electrical") or {}


def packages(device: dict) -> dict:
    return pin_domain(device).get("packages") or device.get("packages") or {}


def electrical_parameters(device: dict) -> dict:
    return (
        electrical_domain(device).get("electrical_parameters")
        or device.get("electrical_parameters")
        or {}
    )


def drc_hints(device: dict) -> dict:
    return electrical_domain(device).get("drc_hints") or device.get("drc_hints") or {}
```

The repository also provides compatibility helpers in
`scripts/device_export_view.py`.

## Common Normal IC Checks

### Pin Lookup

```python
device = load_device("AMS1117")
pkgs = packages(device)

for package_name, package in pkgs.items():
    pin = package["pins"].get("1")
    if pin:
        print(package_name, pin["name"], pin.get("direction"))
```

### Voltage Limit

```python
device = load_device("XL4003")
hints = drc_hints(device)
vin_abs_max = hints.get("vin_abs_max", {}).get("value")

if vin_abs_max is not None and actual_vin > vin_abs_max:
    report_error(f"VIN {actual_vin} V exceeds abs max {vin_abs_max} V")
```

### Feedback Divider

```python
device = load_device("XL4003")
vref = drc_hints(device).get("vref", {}).get("typ")

if vref is not None and r_upper and r_lower:
    vout = vref * (1 + r_upper / r_lower)
```

## Common FPGA Checks

### Physical Pin Lookup

```python
fpga = load_device("XCKU3P", package="FFVB676")
pin_name = fpga["lookup"]["by_pin"].get("AF1")
pin = next((p for p in fpga["pins"] if p["pin"] == "AF1"), None)
```

### Bank Review

```python
bank = fpga["banks"].get("64")
if bank:
    supported = bank.get("supported_vcco") or []
    if supported and actual_vcco not in supported:
        report_error("Bank 64 VCCO is outside supported values")
```

### Differential Pair Completeness

```python
for pair in fpga.get("diff_pairs", []):
    p_used = pair["p_pin"] in connected_pins
    n_used = pair["n_pin"] in connected_pins
    if p_used != n_used:
        report_error(
            f"{pair.get('pair_name')}: only one side connected "
            f"({pair['p_pin']}, {pair['n_pin']})"
        )
```

### Power And Ground Pins

```python
for pin in fpga.get("pins", []):
    if pin.get("function") in {"POWER", "GROUND", "GT_POWER"}:
        if pin["pin"] not in connected_pins:
            report_error(f"Power/ground pin {pin['pin']} {pin['name']} is not connected")
```

## Regeneration

Regenerate public exports from checked-in intermediate data:

```bash
python scripts/export_for_sch_review.py
python scripts/validate_exports.py --summary
```

Regenerate FPGA catalog as part of export generation:

```bash
python scripts/export_for_sch_review.py
```

`scripts/export_for_sch_review.py` is the canonical writer. Do not hand-edit
public exports unless you are doing a temporary investigation and will regenerate
before committing.

## Current Coverage Boundaries

- `register`, `timing`, and `parametric` domains are allowed by schema but have
  no non-empty current public exports.
- `package` has one non-empty current public export.
- `protocol` is currently concentrated in automotive video SerDes profiles.
- FPGA `pin` coverage is strong because package pinout data comes from
  deterministic parser outputs.
