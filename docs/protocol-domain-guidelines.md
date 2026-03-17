# Protocol Domain Guidelines

## Role

The `protocol` domain captures interface-level behavior such as:

- I2C addresses
- SPI mode or command framing
- bus-specific timing or opcode structure

This domain matters for communicative ICs. It does not matter for protection devices and simple discretes.

## Enablement Rule

Only run `protocol` when the datasheet contains a real communication interface. Good signals include:

- interface feature summary
- protocol timing sections
- command or transaction tables
- explicit mentions of I2C, SPI, UART, SMBus, or similar buses

## Common Failure Pattern

A broad selector may confuse:

- command tables with ordering tables
- protocol timing with generic switching plots
- textual bus mentions in applications with actual interface specifications

That produces expensive but low-value extraction.

## Validation Focus

- valid address format
- valid opcode format
- summary consistency, for example `has_i2c` matching actual extracted interfaces
- monotonic timing values when timing-like protocol parameters exist

## Design Rule

Do not use the `protocol` domain to discover whether a device is digital. Use it only after the device class and page content already indicate real bus behavior.
