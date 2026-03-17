# Hardware Best Practice Source Basis

> Official-source baseline used to tighten the hardware-engineering document set in this repo.

## Why this file exists

These hardware docs should not drift into opinion-only writing. This page records the official or primary-source references used as common engineering baselines.

## Power, PDN, and decoupling

- TI power-supply layout training:
  https://www.ti.com/video/6285511636001
- Analog Devices MT-101 Decoupling Techniques:
  https://www.analog.com/media/en/training-seminars/tutorials/MT-101.pdf
- AMD UltraFast methodology excerpt referencing shunt monitoring, PDN simulation, and UG583:
  https://www.xilinx.com/support/documents/sw_manuals/xilinx2022_2/ug949-vivado-design-methodology.pdf
- Altera Signal and Power Integrity Support Center:
  https://www.altera.com/design/resource/signal-integrity/si-pi-overview

## Thermal

- Analog Devices MT-093 Thermal Design Basics:
  https://www.analog.com/media/en/training-seminars/tutorials/MT-093.pdf

## PCB transmission lines and return paths

- Analog Devices MT-094 Microstrip and Stripline Design:
  https://www.analog.com/media/en/training-seminars/tutorials/MT-094.pdf

## I2C

- NXP UM10204 I2C-bus specification and user manual:
  https://www.nxp.com/docs/en/user-guide/UM10204.pdf
- TI Why, When, and How to use I2C Buffers:
  https://www.ti.com/lit/an/scpa054/scpa054.pdf
- TI PCA9515A product guidance:
  https://www.ti.com/product/PCA9515A

## ESD and interface protection

- TI ESD Protection Layout Guide:
  https://www.ti.com/lit/an/slva680/slva680.pdf
- TI ESD Essentials selection training:
  https://www.ti.com/video/5757279989001
- Analog Devices MT-092 Electrostatic Discharge:
  https://www.analog.com/media/en/training-seminars/tutorials/MT-092.pdf

## Reset and sequencing

- TI Power Sequencing With Feedback:
  https://www.ti.com/document-viewer/lit/html/SCLA069
- TI Reset Circuit for the TMS320C6000 DSP:
  https://www.ti.com/jp/lit/pdf/spra431

## FPGA board and high-speed guidance

- Intel reference clock guidance for transceiver tiles:
  https://www.intel.com/content/www/us/en/docs/programmable/683723/current/reference-clocks.html
- Altera board-design resource center for HSSI, EMIF, MIPI, true differential, and PDN:
  https://www.altera.com/design/resource/signal-integrity/si-pi-overview
- TI PCIe training series:
  https://www.ti.com/de-de/video/series/precision-labs/ti-precision-labs-pcie.html
- TI redriver/retimer selection guidance:
  https://www.ti.com/lit/pdf/snla347

## How to use these sources

- Use them to sharpen board-level review questions.
- Do not replace device-specific datasheets with these guides.
- Treat package facts, ordering variants, and measured board conditions as higher priority than family-general guidance.

## Repo rule

When a hardware guideline in this repo conflicts with package-level facts, source the package-level facts first and update the guideline.
