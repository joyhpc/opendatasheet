# Camera Deserializer Ingress Review

> How to review the front edge of a camera ingest board where deserializers, bridges, and FPGA ingress meet.

## Review points

- who owns sensor-side control bus
- how link lock and error reporting are exposed
- what local buffering or elasticity exists after deserialization
- whether power, refclk, and reset assumptions are aligned across the chain

## Common mistakes

- treating deserializer output as clean forever and not budgeting backpressure
- no clear owner for reinit after link disturbance
- no measurement points for lock, clock, or reset state

## Good pattern

Keep ingress modular:
- deserializer health visible
- bridge responsibility clear
- FPGA ingest path testable without the full system

## Official practice baseline

Use system-level architecture review, not just the deserializer datasheet. In these boards, ingress success depends on the chain, not one part.
