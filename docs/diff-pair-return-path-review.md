# Differential Pair Return Path Review

> Differential pairs fail in boards more often from return-path mistakes than from naming mistakes.

## What to review

- uninterrupted reference plane under the pair
- plane transitions with nearby return vias when unavoidable
- connector breakouts that do not create a return-path cliff
- pair spacing and impedance target appropriate to the stackup

## Common mistakes

- assuming differential pairs do not need return-path care
- splitting the pair over a plane gap
- via transitions without nearby stitching or return support
- pushing the pair through a pretty but electrically noisy connector field

## Official practice baseline

Analog Devices MT-094 emphasizes controlled-impedance routing and notes that high-frequency return current lives on adjacent planes. Use that as a baseline before protocol-specific tuning.
