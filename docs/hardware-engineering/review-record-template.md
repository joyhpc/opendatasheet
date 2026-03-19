# 硬件评审记录模板

## 用途

这页不是知识文档，而是给正式硬件评审会议直接套用的记录模板。

建议和 [`formal-review-execution-order.md`](formal-review-execution-order.md) 一起使用。

如果要会前快速扫阻塞项，先看 [`review-gate-matrix.md`](review-gate-matrix.md)。

## 项目信息

- 项目 / 板卡：
- 评审日期：
- 评审版本：
- 参与人：
- 评审范围：

## Phase 1: 系统供电与保护

- 文档入口：
  [`power-tree-review-checklist.md`](power-tree-review-checklist.md)
  [`buck-converter-schematic-review.md`](buck-converter-schematic-review.md)
  [`tvs-and-esd-placement.md`](tvs-and-esd-placement.md)
- 结论（通过 / 带风险通过 / 阻塞）：
- 阻塞项：
- 风险项：
- 最小证据 / 观测点：
- 放行条件：
- 责任人 / 关闭日期：

## Phase 2: 板外接口与总线

- 文档入口：
  [`i2c-pullup-and-topology.md`](i2c-pullup-and-topology.md)
  [`usb2-protection-and-routing.md`](usb2-protection-and-routing.md)
  [`ethernet-phy-bringup-checklist.md`](ethernet-phy-bringup-checklist.md)
- 结论（通过 / 带风险通过 / 阻塞）：
- 阻塞项：
- 风险项：
- 最小证据 / 观测点：
- 放行条件：
- 责任人 / 关闭日期：

## Phase 3: FPGA / DDR / 高速链路

- 文档入口：
  [`fpga-power-rail-planning.md`](fpga-power-rail-planning.md)
  [`fpga-bank-voltage-planning.md`](fpga-bank-voltage-planning.md)
  [`ddr-layout-review-checklist.md`](ddr-layout-review-checklist.md)
  [`differential-pair-routing.md`](differential-pair-routing.md)
- 结论（通过 / 带风险通过 / 阻塞）：
- 阻塞项：
- 风险项：
- 最小证据 / 观测点：
- 放行条件：
- 责任人 / 关闭日期：

## Phase 4: 模拟、采样与热

- 文档入口：
  [`mixed-signal-grounding.md`](mixed-signal-grounding.md)
  [`adc-reference-and-input-drive.md`](adc-reference-and-input-drive.md)
  [`thermal-via-and-copper-spreading.md`](thermal-via-and-copper-spreading.md)
- 结论（通过 / 带风险通过 / 阻塞）：
- 阻塞项：
- 风险项：
- 最小证据 / 观测点：
- 放行条件：
- 责任人 / 关闭日期：

## Phase 5: 制造与工艺

- 文档入口：
  [`manufacturing-dfm-quick-check.md`](manufacturing-dfm-quick-check.md)
- 结论（通过 / 带风险通过 / 阻塞）：
- 阻塞项：
- 风险项：
- 最小证据 / 观测点：
- 放行条件：
- 责任人 / 关闭日期：

## Phase 6: Bring-up 放行条件

- 文档入口：
  [`power-up-debug-sequence.md`](power-up-debug-sequence.md)
- 结论（通过 / 带风险通过 / 阻塞）：
- 阻塞项：
- 风险项：
- 最小证据 / 观测点：
- 放行条件：
- 责任人 / 关闭日期：

## 汇总

- 必须在 layout 前关闭的问题：
- 必须在打样前关闭的问题：
- 必须在 bring-up 前准备的观测点 / 工装：
- 允许带风险前进的事项：
- 明确责任人与关闭时间的事项：
- 最终结论（放行 / 带风险放行 / 不放行）：
