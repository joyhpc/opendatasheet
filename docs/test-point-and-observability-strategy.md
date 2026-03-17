# Test Point And Observability Strategy

> Board-level observability plan for first power-up, link debug, and failure isolation.

## Observe these first

- primary input power
- every critical rail
- key resets
- key clocks and refclks
- at least one ingress and one egress heartbeat

## High-value test points

- rails that gate system life
- configuration-complete or power-good signals
- serializer/deserializer refclk nodes where probing is safe
- MCU-to-FPGA boundary signals

## Common anti-patterns

- only low-speed signals are observable
- rails measurable only at the regulator, not at the load
- high-speed links have no indirect observability path
- firmware logs are expected to replace hardware observability

## Good strategy

Provide a mix of:
- direct measurement nodes
- jumper or resistor option points
- debug headers
- status LEDs only where they clarify, not as the sole instrument

## Official practice baseline

Use `hardware-best-practice-source-basis.md` for the measurement and monitoring references behind this strategy.
