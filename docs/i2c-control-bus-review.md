# I2C Control Bus Review

> Review checklist for control-plane I2C buses on mixed-voltage hardware platforms.

## Review points

- bus voltage and pull-up rail are explicit
- total bus capacitance is credible
- rise-time target matches the selected mode
- address map is collision-free
- any bus buffer or mux has a clear reason

## Common mistakes

- copying pull-up values without checking rise time
- placing multiple domains on one bus without level-shift review
- assuming a long cable or off-board segment behaves like local PCB routing

## Good bus policy

- document bus speed
- document pull-up value and rail
- document all devices on the bus
- document where recovery or segmentation exists

## Official practice baseline

NXP UM10204 remains the primary baseline for bus timing and capacitance assumptions. TI buffer guidance is useful when bus segmentation becomes necessary.
