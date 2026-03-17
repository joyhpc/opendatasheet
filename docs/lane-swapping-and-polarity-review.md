# Lane Swapping And Polarity Review

> How to review whether lane swaps and polarity inversions are deliberate, legal, and still debuggable.

## Review items

- which interfaces permit lane swapping
- which interfaces permit polarity inversion
- which blocks require fixed lane ordering
- where the swap is documented: schematic, constraints, firmware, or all three

## Failure modes

- legal swap at the PHY but undocumented in bring-up notes
- polarity inversion assumed legal on a link that does not support it
- connector pinout forces a swap the device package cannot absorb cleanly

## Good practice

- document the logical order and physical order separately
- tie each swap to one owning document
- keep loopback and probe plans aware of the swap

## Official practice baseline

Transceiver and board-guideline documents from Intel/Altera and AMD repeatedly treat lane access and refclk access as package facts. Review swaps at that level.
