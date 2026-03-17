# 硬件工程最佳实践参考矩阵

## 目的

本目录的 50 篇硬件文档不是凭经验随手写的。它们优先对齐一手资料中的稳定共识，再压缩成适合评审和 bring-up 使用的工程清单。

## 优先参考来源类型

- 芯片厂官方 datasheet、user guide、board design guide
- 官方 application note、precision lab、layout guide
- 协议或总线官方规范
- 存储器、FPGA、PHY 供应商的板级设计指南

## 电源与保护

- TI: switching regulator layout 与 buck layout 应用笔记
- TI: LDO stability / output capacitor 系列文档
- TI: eFuse、hot-swap、inrush control 应用报告
- TI: TVS / ESD layout 与接口保护应用笔记
- ADI: MT-101 Decoupling Techniques

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

- NXP: UM10204 I2C-bus specification
- TI: RS-485 basics / fail-safe bias / termination 应用报告
- Microchip: USB 2.0 hardware design guidelines
- TI / PHY vendors: Ethernet PHY layout 与 strap 设计指南
- AMD / Intel / TI: high-speed reference clock 与 jitter 相关文档

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

- AMD/Xilinx: PCB Design Guide, IO and Clock Planning, GTY/GTH Transceiver User Guide
- Intel: FPGA PCB Design Guidelines
- Micron: DDR layout 与 power delivery 指南
- 高速连接器厂家与板厂 stackup/impedance 工艺约束

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

- ADI: MT-031 Grounding, MT-093 Thermal Design, MT-101 Decoupling
- TI Precision Labs: ADC front-end, thermistor, comparator hysteresis
- 常见 DAC / op amp 官方应用笔记

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
