# 面向硬件工程师的核心文档

## 定位

这一层不再追求“主题全覆盖”，只保留能直接指导一次设计评审、一次 bring-up、一次板级决策的核心文档。

保留标准：

- 必须回答高频问题
- 必须能减少真实错误
- 必须能在项目里直接拿来用

其余泛化、培训式、低上下文绑定的文档已移到 [`archive/`](archive/)。

配套来源见 [`best-practice-reference-matrix.md`](best-practice-reference-matrix.md)。

正式评审顺序见 [`formal-review-execution-order.md`](formal-review-execution-order.md)。

会议记录模板见 [`review-record-template.md`](review-record-template.md)。

放行门槛速查见 [`review-gate-matrix.md`](review-gate-matrix.md)。

## 最先看这 5 篇

- [`power-tree-review-checklist.md`](power-tree-review-checklist.md)  
  电源树 review 的第一入口。适合做系统级 rail 审查。
- [`buck-converter-schematic-review.md`](buck-converter-schematic-review.md)  
  开关电源最常见失误和检查顺序。
- [`differential-pair-routing.md`](differential-pair-routing.md)  
  高速接口和时钟差分对的核心走线规则。
- [`adc-reference-and-input-drive.md`](adc-reference-and-input-drive.md)  
  精密采样和 SAR ADC 前端最容易出错的地方。
- [`power-up-debug-sequence.md`](power-up-debug-sequence.md)  
  新板首电和故障板排查的实际执行顺序。

## 核心主题

### 先排议程

- [`formal-review-execution-order.md`](formal-review-execution-order.md)
- [`review-gate-matrix.md`](review-gate-matrix.md)
- [`review-record-template.md`](review-record-template.md)

### 电源与保护

- [`power-tree-review-checklist.md`](power-tree-review-checklist.md)
- [`buck-converter-schematic-review.md`](buck-converter-schematic-review.md)
- [`tvs-and-esd-placement.md`](tvs-and-esd-placement.md)

### 总线与外部接口

- [`i2c-pullup-and-topology.md`](i2c-pullup-and-topology.md)
- [`usb2-protection-and-routing.md`](usb2-protection-and-routing.md)
- [`ethernet-phy-bringup-checklist.md`](ethernet-phy-bringup-checklist.md)

### FPGA 与高速设计

- [`fpga-power-rail-planning.md`](fpga-power-rail-planning.md)
- [`fpga-bank-voltage-planning.md`](fpga-bank-voltage-planning.md)
- [`ddr-layout-review-checklist.md`](ddr-layout-review-checklist.md)
- [`differential-pair-routing.md`](differential-pair-routing.md)

### 模拟与热

- [`mixed-signal-grounding.md`](mixed-signal-grounding.md)
- [`adc-reference-and-input-drive.md`](adc-reference-and-input-drive.md)
- [`thermal-via-and-copper-spreading.md`](thermal-via-and-copper-spreading.md)

### Bring-up 与制造

- [`power-up-debug-sequence.md`](power-up-debug-sequence.md)
- [`manufacturing-dfm-quick-check.md`](manufacturing-dfm-quick-check.md)

## 使用建议

- 需要快速 review，就只看这一页列出的文档。
- 需要先判断“这板能不能继续往前走”，先看 [`review-gate-matrix.md`](review-gate-matrix.md)。
- 需要把评审结论真正落到会后执行，就同时打开 [`review-record-template.md`](review-record-template.md)。
- 需要追溯官方来源，就看 [`best-practice-reference-matrix.md`](best-practice-reference-matrix.md)。
- 需要查旧主题或泛化材料，再去 [`archive/`](archive/)。
