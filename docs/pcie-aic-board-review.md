# PCIe AIC Board Review

> Review checklist for add-in-card style PCIe boards and mezzanine-like PCIe form factors.

## Review points

- edge connector lane map and sideband signals are explicit
- PERST#, CLKREQ#, WAKE#, and power rails are owned
- reference clock source and distribution are explicit
- any switch, mux, redriver, or retimer is tied to a training strategy

## Common mistakes

- reviewing only lane count, not the full sideband and reset context
- assuming the host always provides a clean reference clock implementation
- forgetting slot power behavior and inrush

## Good bring-up plan

- power-only validation
- refclk validation
- endpoint reset validation
- training visibility before full software stack

## Official practice baseline

Use TI PCIe training and signal-conditioning guidance together with board-specific slot and connector requirements.
