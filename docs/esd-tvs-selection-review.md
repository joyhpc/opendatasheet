# ESD TVS Selection Review

> How to review ESD and TVS choices so they protect the interface instead of just decorating the BOM.

## Selection questions

- what is the normal working voltage
- what polarity and event model matter
- how much line capacitance can the interface tolerate
- where is the protector placed relative to the connector

## Layout matters as much as part selection

- place the device close to the entry point
- keep discharge path short
- keep the protected node from taking the long return route first

## Common mistakes

- selecting a protector by clamp voltage alone
- putting the device far from the connector
- ignoring capacitance on high-speed or analog-sensitive lines

## Official practice baseline

TI’s ESD layout guidance is especially clear: protection effectiveness collapses when the return path and placement are wrong. ADI MT-092 is also useful for grounding the physical failure mechanisms.
