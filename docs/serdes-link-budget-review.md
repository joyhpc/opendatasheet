# SerDes Link Budget Review

> How to review high-speed serial links as end-to-end budgets rather than device headline rates.

## Budget components

- package escape
- PCB insertion loss
- via discontinuities
- connectors
- redrivers, retimers, or switches
- receiver margin
- refclk quality

## Red flags

- channel loss unknown
- only a connector datasheet exists, no system estimate
- equalization expected to solve topology problems
- shared refclk path assumed valid across incompatible groups

## Good practice

- estimate channel loss at the relevant Nyquist point
- identify where jitter is being added
- know whether link training is required
- know which observability exists before protocol stack is alive

## Official practice baseline

TI retimer/redriver guidance and Intel/Altera signal-integrity resources both push designers toward channel-loss awareness, simulation, and refclk-aware planning.
