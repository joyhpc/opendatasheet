# CXD4984ER-W Downstream Handoff

## Files

- Normalized export: `/home/ubuntu/opendatasheet/.tmp/cxd4984/export/CXD4984ER-W.json`
- Focused extraction: `/home/ubuntu/opendatasheet/.tmp/cxd4984/CXD4984ER.focused.json`
- Raw text index: `/home/ubuntu/opendatasheet/.tmp/cxd4984/CXD4984ER.txt`
- Decrypted PDF: `/home/ubuntu/opendatasheet/data/raw/_staging/CXD4984ER.decrypted.pdf`

## What Downstream Can Read Directly

- Package and pins:
  - `packages.VQFN-64.pin_count`
  - `packages.VQFN-64.pins`
- Electrical limits and operating ranges:
  - `absolute_maximum_ratings`
  - `electrical_parameters`
- Package metadata:
  - `domains.package.packages`
  - `domains.package.package_summary`

## Recommended Field Mapping

- Core 1.1 V rail:
  - `electrical_parameters["VDD11, VDD11A_G3TX, VDD11A_G3TXP, VDD11A_G3RX, VDD11A_MIPITX0, VDD11A_MIPITX1"]`
- 1.8 V analog rail:
  - `electrical_parameters["VDD18A_G3RX, VDD18A_MIPITX0, VDD18A_MIPITX1"]`
- IO rail:
  - `electrical_parameters["VDDIO (When setting 1.8 V interface)"]`
  - `electrical_parameters["VDDIO (When setting 3.3 V interface)"]`
- I2C thresholds:
  - `electrical_parameters["VIH_I2C"]`
  - `electrical_parameters["VIL_I2C"]`
- Supply current:
  - `electrical_parameters["ICC_1.1V"]`
  - `electrical_parameters["ICC_1.8V"]`
  - `electrical_parameters["ICC_IO"]`
- D-PHY rate:
  - `electrical_parameters["DR_MIPI"]`
  - `electrical_parameters["DR_MIPI_4_Lanes"]`
- Reset / control / address select pins:
  - `packages.VQFN-64.pins["26"]` = `CE`
  - `packages.VQFN-64.pins["18"]` = `SCL0`
  - `packages.VQFN-64.pins["19"]` = `SDA0`
  - `packages.VQFN-64.pins["32"]` = `I2CADR`
  - `packages.VQFN-64.pins["20".."25"]` = `GENERAL_IO*` / control mux pins

## Facts That Are Authoritative But Not Yet Fully Structured In Export

- D-PHY:
  - 2 ports
  - 4 data lanes per port + 1 clock lane
  - D-PHY v2.1
  - CSI-2 v2.1
  - 260 to 4500 Mbps/lane
  - Source pages: 41, 42, 24
- C-PHY:
  - 2 ports
  - 3 lanes per port
  - Treat as 3 trios per port for system decision-making
  - C-PHY v1.2
  - CSI-2 v2.1
  - 300 to 4500 Msps/lane
  - Source pages: 46, 47, 49
- C-PHY/D-PHY rate conversion note:
  - see page 54 formula for fixed clock mode

## Consumer Guidance

- For `sch-review`:
  - use the normalized export JSON as the primary source for pins, rails, and control signals
  - do not infer C-PHY trio count from pin names alone; use the page-backed facts above
- For `CAMRX` / `requirements.yaml`:
  - use page-backed facts above for the C-PHY vs D-PHY decision
  - use export JSON for rails, I2C, reset, package, and pin ownership

## Current Limitation

- The export does not yet expose the C-PHY max symbol rate as a dedicated structured field.
- Until that is added, downstream should consume the page-backed fact:
  - `C-PHY symbol/data rate range: 300..4500 Msps/lane`
  - `3 trios per port, 2 ports total`
