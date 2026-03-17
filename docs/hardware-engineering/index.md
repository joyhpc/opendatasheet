# 面向硬件工程师的文档库

## 定位

这一组文档面向做原理图、layout 约束、器件选型、bring-up 和设计评审的硬件工程师。

写法目标不是百科式展开，而是：

- 让你在评审时知道先看什么
- 让你在 bring-up 时知道先量什么
- 让你在接口和电源设计时少踩明显坑

目录中的规则优先对齐官方用户指南、应用笔记和协议规范，再压缩成能直接拿去用的检查项。

配套参考见 [`best-practice-reference-matrix.md`](best-practice-reference-matrix.md)。

## 电源与保护

- [`power-tree-review-checklist.md`](power-tree-review-checklist.md)
- [`decoupling-capacitor-placement.md`](decoupling-capacitor-placement.md)
- [`ldo-selection-and-stability.md`](ldo-selection-and-stability.md)
- [`buck-converter-schematic-review.md`](buck-converter-schematic-review.md)
- [`load-switch-and-hot-swap.md`](load-switch-and-hot-swap.md)
- [`tvs-and-esd-placement.md`](tvs-and-esd-placement.md)
- [`reverse-polarity-and-surge-protection.md`](reverse-polarity-and-surge-protection.md)
- [`mosfet-gate-drive-basics.md`](mosfet-gate-drive-basics.md)
- [`current-sense-shunt-layout.md`](current-sense-shunt-layout.md)
- [`efuse-and-inrush-control.md`](efuse-and-inrush-control.md)

## 接口与时钟

- [`i2c-pullup-and-topology.md`](i2c-pullup-and-topology.md)
- [`spi-bus-review-guide.md`](spi-bus-review-guide.md)
- [`uart-rs485-interface-design.md`](uart-rs485-interface-design.md)
- [`usb2-protection-and-routing.md`](usb2-protection-and-routing.md)
- [`ethernet-phy-bringup-checklist.md`](ethernet-phy-bringup-checklist.md)
- [`mipi-csi-dsi-board-guide.md`](mipi-csi-dsi-board-guide.md)
- [`serdes-gmsl-fpdlink-checklist.md`](serdes-gmsl-fpdlink-checklist.md)
- [`clock-oscillator-selection.md`](clock-oscillator-selection.md)
- [`pll-jitter-budget-basics.md`](pll-jitter-budget-basics.md)
- [`reset-and-supervisor-design.md`](reset-and-supervisor-design.md)

## FPGA 与高速设计

- [`fpga-power-rail-planning.md`](fpga-power-rail-planning.md)
- [`fpga-bank-voltage-planning.md`](fpga-bank-voltage-planning.md)
- [`fpga-configuration-and-jtag.md`](fpga-configuration-and-jtag.md)
- [`fpga-transceiver-reference-clock.md`](fpga-transceiver-reference-clock.md)
- [`ddr-power-sequencing.md`](ddr-power-sequencing.md)
- [`ddr-layout-review-checklist.md`](ddr-layout-review-checklist.md)
- [`differential-pair-routing.md`](differential-pair-routing.md)
- [`impedance-stackup-handoff.md`](impedance-stackup-handoff.md)
- [`mixed-signal-grounding.md`](mixed-signal-grounding.md)
- [`high-speed-connector-escape.md`](high-speed-connector-escape.md)

## 模拟、采样与热

- [`opamp-front-end-review.md`](opamp-front-end-review.md)
- [`comparator-threshold-and-hysteresis.md`](comparator-threshold-and-hysteresis.md)
- [`adc-reference-and-input-drive.md`](adc-reference-and-input-drive.md)
- [`dac-output-buffering.md`](dac-output-buffering.md)
- [`sensor-excitation-and-ratiometric.md`](sensor-excitation-and-ratiometric.md)
- [`thermistor-and-ntc-interface.md`](thermistor-and-ntc-interface.md)
- [`current-loop-4-20ma-front-end.md`](current-loop-4-20ma-front-end.md)
- [`thermal-via-and-copper-spreading.md`](thermal-via-and-copper-spreading.md)
- [`package-thermal-resistance-usage.md`](package-thermal-resistance-usage.md)
- [`fan-pwm-and-tachometer.md`](fan-pwm-and-tachometer.md)

## 评审、制造与 Bring-up

- [`test-point-strategy.md`](test-point-strategy.md)
- [`bringup-lab-instrumentation.md`](bringup-lab-instrumentation.md)
- [`power-up-debug-sequence.md`](power-up-debug-sequence.md)
- [`schematic-page-organization.md`](schematic-page-organization.md)
- [`net-naming-and-rail-conventions.md`](net-naming-and-rail-conventions.md)
- [`component-derating-guide.md`](component-derating-guide.md)
- [`second-source-and-bom-risk.md`](second-source-and-bom-risk.md)
- [`design-review-severity-model.md`](design-review-severity-model.md)
- [`manufacturing-dfm-quick-check.md`](manufacturing-dfm-quick-check.md)
- [`pre-layout-post-layout-handoff.md`](pre-layout-post-layout-handoff.md)
