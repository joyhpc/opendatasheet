# Rail Sequencing Review

> How to review whether power rails come up in a survivable and debuggable order.

## Review targets

- power-good dependencies
- enable chains
- supervisor thresholds
- reset release timing
- FPGA or SoC special sequencing constraints

## Good sequencing questions

- which rails must be valid before configuration starts
- what happens if one secondary rail lags
- can a regulator partially start and leave logic in undefined state
- does the reset tree actually wait for usable rails, not just any rail

## Frequent mistakes

- power-good used as logic truth without timing review
- reset released before reference clock is valid
- analog rail brought up too late for serializer/deserializer biasing
- “works on bench” because startup source is unrealistically slow

## What to document

- rail order
- nominal delay windows
- dependencies
- measurement points
- abnormal-start behavior

## Repo tie-in

As `power_sequence` coverage grows, use this repo to carry structured sequence facts. Until then, treat sequence as a board-level review artifact first.

## Official practice baseline

Use `hardware-best-practice-source-basis.md` for sequencing and reset references.
