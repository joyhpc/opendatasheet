# Bank VCCO Planning

> Review method for FPGA I/O bank voltage planning before the schematic becomes too expensive to fix.

## Core questions

- what standards live in each bank
- what VCCO does each bank require
- which pins are package-specific escape constraints
- which banks are being consumed by future options already

## Common mistakes

- placing pins first and assigning VCCO later
- mixing current and future interfaces in one bank without margin
- assuming family capability means this package can host the mix cleanly

## Use this repo for

- bank inventory from FPGA exports
- package pin lookup
- diff-pair and refclk awareness

## Official practice baseline

Intel’s GPIO design guidance highlights VCCIO compatibility, unused bank handling, and power-sequencing implications. AMD guidance similarly ties power, decoupling, and package planning together. Use package-level exports plus the source basis doc, not family marketing summaries.
