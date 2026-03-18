# 硬件工程最佳实践参考矩阵

## 目的

本目录的 50 篇硬件文档不是凭经验随手写的。它们优先对齐一手资料中的稳定共识，再压缩成适合评审和 bring-up 使用的工程清单。

## 优先参考来源类型

- 芯片厂官方 datasheet、user guide、board design guide
- 官方 application note、precision lab、layout guide
- 协议或总线官方规范
- 存储器、FPGA、PHY 供应商的板级设计指南

## 电源与保护

- ADI: [`MT-101 Decoupling Techniques`](https://www.analog.com/media/en/training-seminars/tutorials/mt-101.pdf)
- ADI: [`MT-093 Thermal Design Basics`](https://www.analog.com/media/en/training-seminars/tutorials/MT-093.pdf)
- ADI: [`Practical Design Techniques for Power and Thermal Management`](https://www.analog.com/en/resources/technical-books/practical-design-techniques-power-thermal-management.html)
- TI: 开关电源与 buck 布局指导，典型入口可从 [`LM2576HV datasheet` 的 Layout Guidelines](https://www.ti.com/lit/gpn/LM2576HV) 延伸到同类 regulator 应用笔记
- TI: LDO 稳定性与输出电容行为，至少要回到具体 LDO datasheet 的 stability 条件，例如 [`TPS715-Q1`](https://www.ti.com/product/TPS715-Q1)

映射文档：

- `power-tree-review-checklist.md`
- `decoupling-capacitor-placement.md`
- `ldo-selection-and-stability.md`
- `buck-converter-schematic-review.md`
- `load-switch-and-hot-swap.md`
- `tvs-and-esd-placement.md`
- `reverse-polarity-and-surge-protection.md`
- `mosfet-gate-drive-basics.md`
- `current-sense-shunt-layout.md`
- `efuse-and-inrush-control.md`

## 接口与时钟

- NXP: [`UM10204 I2C-bus specification and user manual`](https://www.nxp.com/docs/en/user-guide/UM10204.pdf)
- TI: [`RS-485 Basics: Introduction`](https://www.ti.com/document-viewer/lit/html/ssztcs4)
- TI: [`RS-485 Design Guide (SLLA272)`](https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/142/6683.RS485-Design-guide_5F00_slla272b.pdf)
- Microchip: [`USB Device Design Checklist`](https://www.microchip.com/en-us/application-notes/an2621)
- Microchip: [`USB333x Transceiver Layout Guidelines`](https://www.microchip.com/en-us/application-notes/an204)
- Microchip: [`Implementation Guidelines for Microchip USB 2.0/3.1 Gen 1 Hub Devices`](https://ww1.microchip.com/downloads/aemDocuments/documents/UNG/ApplicationNotes/ApplicationNotes/AN26.2-Application-Note-DS00001876.pdf)

映射文档：

- `i2c-pullup-and-topology.md`
- `spi-bus-review-guide.md`
- `uart-rs485-interface-design.md`
- `usb2-protection-and-routing.md`
- `ethernet-phy-bringup-checklist.md`
- `mipi-csi-dsi-board-guide.md`
- `serdes-gmsl-fpdlink-checklist.md`
- `clock-oscillator-selection.md`
- `pll-jitter-budget-basics.md`
- `reset-and-supervisor-design.md`

## FPGA 与高速设计

- AMD/Xilinx: `UG899 Vivado Design Suite User Guide: I/O and Clock Planning`
- AMD/Xilinx: `UG578 UltraScale Architecture GTY Transceivers User Guide`
- Intel: [`PCB Design Guidelines (HSSI, EMIF, MIPI, True Differential, PDN) User Guide: Agilex 5`](https://www.intel.com/content/www/us/en/docs/programmable/821801/current/power-distribution-network-design-guidelines-01408.html)
- Intel: [`F-Tile PCB Design Guidelines`](https://www.intel.com/content/www/us/en/docs/programmable/683864/current/f-tile-pcb-design-guidelines.html)
- Intel: [`Agilex 7 Power Distribution Network Design Guidelines`](https://www.intel.com/content/www/us/en/docs/programmable/683393/current/board-power-delivery-network-simulations.html)
- Intel: [`AN 875: Intel Stratix 10 E-Tile PCB Design Guidelines`](https://www.intel.com/content/www/us/en/docs/programmable/683262/current/fpga-pcb-design.html)
- Intel: [`DDR5 Board Design Guidelines`](https://www.intel.com/content/www/us/en/docs/programmable/772538/25-1/ddr5-board-design-guidelines.html)
- Intel: `AN 754: MIPI D-PHY Solution with Passive Resistor Networks in Intel Low-Cost FPGAs`

映射文档：

- `fpga-power-rail-planning.md`
- `fpga-bank-voltage-planning.md`
- `fpga-configuration-and-jtag.md`
- `fpga-transceiver-reference-clock.md`
- `ddr-power-sequencing.md`
- `ddr-layout-review-checklist.md`
- `differential-pair-routing.md`
- `impedance-stackup-handoff.md`
- `mixed-signal-grounding.md`
- `high-speed-connector-escape.md`

## 模拟、采样与热

- ADI: [`MT-031 Grounding Data Converters and Solving the Mystery of AGND and DGND`](https://www.analog.com/media/en/training-seminars/tutorials/MT-031.pdf)
- ADI: [`MT-093 Thermal Design Basics`](https://www.analog.com/media/en/training-seminars/tutorials/MT-093.pdf)
- ADI: [`MT-101 Decoupling Techniques`](https://www.analog.com/media/en/training-seminars/tutorials/mt-101.pdf)
- ADI: [`CN0314 4-20 mA Loop Powered Transmitter/Receiver`](https://www.analog.com/en/resources/reference-designs/circuits-from-the-lab/cn0314.html)
- ADI: [`CN0201 multiplexed data acquisition system`](https://www.analog.com/en/resources/reference-designs/circuits-from-the-lab/cn0201.html)
- TI: [`Comparator with and without hysteresis`](https://www.ti.com/tool/CIRCUIT060073)
- TI: [`Comparator with Hysteresis Reference Design`](https://www.ti.com/tool/TIPD144)

映射文档：

- `opamp-front-end-review.md`
- `comparator-threshold-and-hysteresis.md`
- `adc-reference-and-input-drive.md`
- `dac-output-buffering.md`
- `sensor-excitation-and-ratiometric.md`
- `thermistor-and-ntc-interface.md`
- `current-loop-4-20ma-front-end.md`
- `thermal-via-and-copper-spreading.md`
- `package-thermal-resistance-usage.md`
- `fan-pwm-and-tachometer.md`

## 评审、制造与 bring-up

- PCB 厂 DFM 指南
- SMT 工艺设计规范
- FPGA / SoC 板卡 bring-up 常见流程
- 量产工程和测试可达性最佳实践

映射文档：

- `test-point-strategy.md`
- `bringup-lab-instrumentation.md`
- `power-up-debug-sequence.md`
- `schematic-page-organization.md`
- `net-naming-and-rail-conventions.md`
- `component-derating-guide.md`
- `second-source-and-bom-risk.md`
- `design-review-severity-model.md`
- `manufacturing-dfm-quick-check.md`
- `pre-layout-post-layout-handoff.md`

## 使用建议

- 当你需要快速做 review，用各主题文档本身。
- 当你需要追溯“这条规则来自哪类官方经验”，回到本矩阵。
- 当某类器件明显偏离这些规则时，优先查看该器件的官方 datasheet 和 eval board 资料，而不是强行套目录里的通用经验。
