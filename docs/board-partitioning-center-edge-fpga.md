# Board Partitioning Center Edge FPGA

> How to decide what belongs in the center FPGA and what should stay at the edge.

## Center FPGA is for

- aggregation
- heavy local processing
- main DDR coupling
- main high-speed egress coupling
- system-level coordination

## Edge FPGA is for

- protocol adaptation
- lane remap
- local bridge behavior
- low-cost containment of interface-specific complexity

## Bad patterns

- pushing everything into the center and exploding risk
- making every edge board as heavy as the center
- using the same family everywhere for organizational neatness rather than system fit

## Good review question

Which layer should own this complexity so that one bad assumption does not destabilize the whole platform?

## Official practice baseline

This aligns strongly with the A57 architecture notes: center layers need stability and mainline margin, edge layers need focused protocol convergence.
