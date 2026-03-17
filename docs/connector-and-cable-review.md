# Connector And Cable Review

> Review method for connectors and cables as electrical elements, not only mechanical choices.

## Questions to ask

- what signals cross the boundary
- what return path crosses with them
- what ESD event reaches the board here
- what insertion loss or skew is added
- what hot-plug or mate-first-break-last assumptions exist

## Common mistakes

- connector chosen by pin count and pitch only
- cable assembly assumed ideal
- sideband and shield termination left ambiguous
- no serviceability path when the cable is partially inserted or damaged

## Good review artifacts

- pinout table
- shield and chassis termination plan
- mating-order notes if power is involved
- high-speed loss and skew assumptions

## Official practice baseline

For any external boundary, combine ESD layout guidance, interface-specific SI guidance, and the real connector vendor data.
