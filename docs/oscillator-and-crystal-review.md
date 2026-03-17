# Oscillator And Crystal Review

> Practical review of clock source implementation, not just BOM presence.

## Ask these first

- is this node using an oscillator or a crystal network
- what startup time does the system assume
- what load and bias requirements does the source impose
- is the output format compatible with the consuming device

## Oscillator review

- output standard matches receiver expectation
- power rail is clean enough for jitter requirements
- enable pin behavior is known
- startup time is reflected in reset sequencing

## Crystal review

- load capacitors are based on target load, not copied blindly
- drive level is within the source and receiver expectations
- routing is short, quiet, and symmetric enough
- there is no accidental debug or probing strategy that destroys the node

## Common mistakes

- oscillator footprint chosen without checking package pinout options
- crystal network copied across devices with different internal caps
- startup assumptions hidden in firmware timing constants

## When to escalate

Escalate if the clock feeds:
- FPGA configuration logic
- DDR reference infrastructure
- serializer/deserializer reference domains

## Official practice baseline

Use `hardware-best-practice-source-basis.md` and then the device-specific oscillator, crystal, or FPGA clocking documentation.
