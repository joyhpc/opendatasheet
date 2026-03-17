# Power Rail Measurement Plan

> Measurement plan for first power-up, rail debug, and repeatable lab validation.

## Every critical rail should have

- nominal voltage target
- expected ramp behavior
- acceptable ripple or droop expectation
- measurement location
- instrument method

## Good measurement locations

- at the regulator output
- at the primary load cluster
- across shunts or current-sense elements where present

## Common mistakes

- measuring only at the regulator and declaring success
- no current measurement path on critical rails
- no way to separate sequencing failure from load-short failure

## Good practice

- identify rails that need current observation
- identify rails that gate reset or boot
- identify rails where dynamic load matters

## Official practice baseline

AMD methodology notes explicitly call out shunt resistors and power-rail monitoring as part of system debug. Treat that as standard practice on valuable complex boards.
