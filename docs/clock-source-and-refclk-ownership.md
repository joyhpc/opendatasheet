# Clock Source And Refclk Ownership

> How to review clocks as ownership problems, not just frequency labels.

## Every clock should have an owner

For each clock or refclk, define:
- who generates it
- who conditions it
- who distributes it
- which consumers are mandatory
- how it is observed during bring-up

## Why ownership matters

Many board failures are not “wrong frequency” failures. They are:
- wrong source connected to the right net name
- right source with wrong startup assumption
- clock reaching some consumers but not all
- refclk physically valid but not usable for the intended lane group

## High-speed-specific checks

- transceiver lane groups and refclk pairs are mapped explicitly
- switch or mux insertion loss is reviewed
- oscillator stuffing options are not left vague
- fallback clock path exists or is intentionally absent

## Architecture lesson

For SerDes, the real risk is often:
- refclk ownership
- connector path
- assembly option
- test loop closure

not the transceiver headline rate.

## Repo tie-in

For FPGA exports, use:
- `diff_pairs`
- `constraint_blocks.refclk_requirements`
- package-specific pin facts

## Official practice baseline

Use `hardware-best-practice-source-basis.md` for Intel/Altera and AMD clock and refclk references.
