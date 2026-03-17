# MIPI D-PHY Board Review

> Review checklist for MIPI ingress paths before they become routing debt.

## Questions that matter

- are D-PHY-capable pins on the actual device and package being used
- do clock and data lanes have realistic escape and reference-plane support
- is lane count being confused with implementable bank topology
- what burst behavior hits local buffering and downstream egress

## Board-level traps

- routing MIPI as if it were generic LVDS
- forcing MIPI into banks already crowded by control IO or DDR
- ignoring skew and return-path quality during connector escape

## Architecture rule

Ingress review must include:
- lane/bank/package fit
- local buffer margin
- downstream consumer path

not just the camera-side connector.

## Official practice baseline

Use A57 architecture notes plus Intel/Altera guided resources for MIPI board design. Package-specific implementation still wins over family claims.
