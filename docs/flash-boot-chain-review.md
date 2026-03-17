# Flash Boot Chain Review

> Review checklist for configuration flash, boot straps, and recovery behavior.

## Review points

- default boot source is explicit
- flash voltage and IO standard match the consumer
- reset and clock timing permit valid boot sampling
- alternate boot or recovery path exists if flash is corrupted

## Common mistakes

- flash part chosen before configuration mode is frozen
- boot straps share debug or GPIO pins with unclear defaults
- no recovery path when primary flash image is invalid

## Good board policy

- document default straps
- document programming path
- document recovery path
- document which rails and clocks must be valid before boot sampling

## For FPGA boards

Also ask:
- does JTAG recovery remain possible
- are mode pins observable or at least inferable on assembled boards
