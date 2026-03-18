# 核心硬件文档参考矩阵

## 目的

这份矩阵只服务当前保留的核心文档集，不再为归档区的泛化文档做导航。

原则：

- 优先官方 datasheet、user guide、application note、协议规范
- 优先能直接支持 review 和 bring-up 的材料
- 优先与当前保留文档一一对应

## 电源与保护

### `power-tree-review-checklist.md`

- ADI: [`MT-101 Decoupling Techniques`](https://www.analog.com/media/en/training-seminars/tutorials/mt-101.pdf)
- ADI: [`MT-093 Thermal Design Basics`](https://www.analog.com/media/en/training-seminars/tutorials/MT-093.pdf)

### `buck-converter-schematic-review.md`

- TI: 具体 buck regulator datasheet 中的 `Layout Guidelines` 段，例如 [`LM2576HV`](https://www.ti.com/lit/gpn/LM2576HV)
- TI: 同类 switching regulator layout / current loop 应用笔记

### `tvs-and-esd-placement.md`

- 接口芯片官方 ESD/TVS layout 推荐
- 连接器和 PHY 厂商的板级保护参考设计

## 总线与外部接口

### `i2c-pullup-and-topology.md`

- NXP: [`UM10204 I2C-bus specification and user manual`](https://www.nxp.com/docs/en/user-guide/UM10204.pdf)

### `usb2-protection-and-routing.md`

- Microchip: [`USB Device Design Checklist`](https://www.microchip.com/en-us/application-notes/an2621)
- Microchip: [`USB333x Transceiver Layout Guidelines`](https://www.microchip.com/en-us/application-notes/an204)
- Microchip: [`Implementation Guidelines for Microchip USB 2.0/3.1 Gen 1 Hub Devices`](https://ww1.microchip.com/downloads/aemDocuments/documents/UNG/ApplicationNotes/ApplicationNotes/AN26.2-Application-Note-DS00001876.pdf)

### `ethernet-phy-bringup-checklist.md`

- 各 PHY 官方 reference schematic、strap timing、layout guide
- TI / Microchip / Realtek / Marvell PHY 参考设计

## FPGA 与高速设计

### `fpga-power-rail-planning.md`

- Intel: [`PCB Design Guidelines (HSSI, EMIF, MIPI, True Differential, PDN) User Guide: Agilex 5`](https://www.intel.com/content/www/us/en/docs/programmable/821801/current/power-distribution-network-design-guidelines-01408.html)
- Intel: [`Agilex 7 Power Distribution Network Design Guidelines`](https://www.intel.com/content/www/us/en/docs/programmable/683393/current/board-power-delivery-network-simulations.html)

### `fpga-bank-voltage-planning.md`

- AMD/Xilinx: `UG899 Vivado Design Suite User Guide: I/O and Clock Planning`
- Intel: 各 FPGA family 的 IO bank / VCCIO 规划指南

### `ddr-layout-review-checklist.md`

- Intel: [`DDR5 Board Design Guidelines`](https://www.intel.com/content/www/us/en/docs/programmable/772538/25-1/ddr5-board-design-guidelines.html)
- Micron / controller vendor 的 DDR layout 与 topology 指南

### `differential-pair-routing.md`

- FPGA、PHY、SerDes、connector 厂商的 differential routing guide
- Stackup/impedance 由 PCB 厂工艺约束共同决定

## 模拟与热

### `mixed-signal-grounding.md`

- ADI: [`MT-031 Grounding Data Converters and Solving the Mystery of AGND and DGND`](https://www.analog.com/media/en/training-seminars/tutorials/MT-031.pdf)

### `adc-reference-and-input-drive.md`

- ADI: ADC front-end reference designs and tutorials
- TI Precision Labs ADC 驱动与参考设计资料

### `thermal-via-and-copper-spreading.md`

- ADI: [`MT-093 Thermal Design Basics`](https://www.analog.com/media/en/training-seminars/tutorials/MT-093.pdf)
- 功率器件 datasheet 中的 exposed pad / thermal layout 推荐

## Bring-up 与制造

### `power-up-debug-sequence.md`

- 板卡 bring-up checklists
- FPGA/SoC eval board user guide 中的 power-up / debug 顺序

### `manufacturing-dfm-quick-check.md`

- PCB 厂 DFM 设计规则
- SMT 厂对细间距、热焊盘、测试点和返修可达性的工艺要求

## 归档说明

这份矩阵不再覆盖 [`archive/`](archive/) 里的文档。归档内容保留历史，但不再作为默认推荐实践。
