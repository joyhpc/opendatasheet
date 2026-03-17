# Reset And Supervisor Review

> Review checklist for reset trees, reset ICs, and release behavior.

## Every reset tree should answer

- what creates reset
- which rails must be valid before release
- what polarity each consumer expects
- what pull state exists when the source is absent
- how manual and automatic reset interact

## Good supervisor checks

- threshold matches the rail that actually matters
- timeout is long enough for clocks and rails, not just one of them
- open-drain and push-pull assumptions are explicit

## Board-level mistakes

- one reset net reused for unrelated domains
- reset released before FPGA refclk or flash path is ready
- MCU supervisor selected correctly but FPGA config path ignored
- RC-only reset used where stateful sequencing is required

## Bring-up rule

You should be able to observe:
- reset asserted
- reset source validity
- release timing relative to rails and clocks

If you cannot measure that, your reset design is under-instrumented.

## Official practice baseline

Use `hardware-best-practice-source-basis.md` for reset and sequencing references.
