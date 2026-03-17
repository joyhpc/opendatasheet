# Thermal Risk Review

> Thermal review questions that should exist before layout and long before chamber testing.

## Ask early

- where is the real power density
- what rails and workloads create worst-case heating
- which components are thermally coupled in placement
- what happens during sustained high-speed operation, not only idle bring-up

## Common mistakes

- reviewing thermal after floorplan is effectively fixed
- using ambient-only thinking on enclosed systems
- treating FPGA GT or memory interface workloads as if they were average-case

## Good inputs

- estimated rail power
- workload modes
- package thermal resistance
- airflow assumption
- allowable case or junction rise

## Official practice baseline

Analog Devices MT-093 is a good reminder that thermal design starts with power and resistance paths, not only heatsink selection. AMD methodology guidance likewise ties power estimation to implementation planning.
