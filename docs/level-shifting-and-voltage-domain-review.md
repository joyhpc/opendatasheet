# Level Shifting And Voltage Domain Review

> How to review digital boundaries between voltage domains before they turn into field failures.

## Review questions

- which side drives and which side receives
- are signals push-pull, open-drain, analog-like, or timing-sensitive
- is translation required in both directions or one
- what is the default state during partial power-up

## Common mistakes

- using a generic translator on a timing-sensitive or bidirectional signal
- forgetting partial-power-down behavior
- translating clocks or resets with inappropriate parts

## Good rule

Do not choose a level shifter by voltage only. Choose it by:
- directionality
- timing
- default state
- power sequencing behavior

## Repo tie-in

Use exported pin direction and function data to identify where translation is even plausible before schematic review goes deeper.
