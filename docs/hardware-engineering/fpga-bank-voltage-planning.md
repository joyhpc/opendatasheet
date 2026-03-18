# FPGA Bank 电压规划

## 适用场景

适用于：

- FPGA pin planning
- IO 标准分组
- 原理图阶段的 bank / package 资源分配
- 高速接口、DDR、MIPI、LVDS、普通 GPIO 混合设计

## 不适用场景

不适用于已经完成 pin assignment、bank 电压已锁死的后期修补阶段。本文是前期约束文档。

## 典型失效症状

Bank 规划做错，后果通常不是“完全不能用”，而是：

- pin 数足够，但 IO 标准不兼容
- 某个接口能接进去，但把另一类接口逼到不可用 bank
- 后期发现 DDR、MIPI、LVDS、GPIO 在同一 bank 互相冲突
- 包装变体切换时，bank 资源完全不可迁移
- bring-up 阶段出现电平不兼容、VREF 不足、差分资源不够

## 先看什么

先做三件事：

1. 列出所有接口和它们要求的电压域、差分资源、VREF、时钟资源。
2. 列出每个 bank 的可用能力，而不是只列球位数量。
3. 先画 bank 分配草图，再开始详细原理图连接。

## 必查顺序

### 1. 接口需求

- 每个接口需要的 `VCCIO`、IO 标准、单端/差分、时钟资源是否明确。
- 哪些接口必须同 bank，哪些接口必须隔离 bank。

### 2. bank 资源

- 每个 bank 的目标电压是否明确。
- 差分对、VREF、专用时钟脚、配置脚是否提前锁定。
- 是否存在“球位够，但资源类型不对”的假象。

### 3. 包装与迁移

- 当前封装和潜在替代封装的 bank 资源是否兼容。
- 未来变型时是预留 bank，还是把所有 bank 都塞满。
- debug、strap、量产 IO 是否分层，而不是随意混放。

### 4. 风险交叉检查

- DDR、MIPI、LVDS、普通 GPIO 是否被错误混在同一 bank。
- 跨 bank 总线是否会引入同步、延迟或 SI 风险。
- 是否因为一个接口的临时方便，牺牲了整体电压规划。

## 硬规则

- Bank 电压规划必须在原理图冻结前完成。
- 不能只看球位数量，必须同时看 `VCCIO`、差分资源、VREF、专用脚。
- 高速接口不允许只因为“刚好有空 pin”就塞进某个 bank。
- 未来变型和 debug 需求必须在 bank 规划阶段预留，而不是后补。
- 如果一个 bank 的目标电压说不清，这个 bank 就不该开始连线。

## 常见失误

- 原理图阶段不做 bank 规划，寄希望于后期工具自动解决。
- 只按 pin 数量分配接口，不看专用资源。
- 把 debug IO、strap IO、量产功能 IO 混放，后期状态互相干扰。

## 评审示例

例子：

- 一个 bank 里同时想放 LVDS、普通 3.3 V GPIO、调试 strap 和未来扩展接口
- 当前封装球位看起来够用
- 但 `VCCIO` 目标、电平、VREF 和差分资源并未先锁定

正式 review 时，应直接给出：

- `ERROR`: bank 目标电压未锁定前，不应冻结该 bank 连线。
- `ERROR`: 把高速接口、普通 GPIO、strap 混放在同一未约束 bank，不应放行。
- `WARNING`: 若未来封装迁移未评估，当前 pin planning 不具备变型韧性。

这种问题如果拖到 layout 或 pin assignment 工具里，返工成本通常最高。

## 仓库入口

- 硬件文档总入口：[`index.md`](index.md)
- 上游电源主题：[`fpga-power-rail-planning.md`](fpga-power-rail-planning.md)
- 来源矩阵：[`best-practice-reference-matrix.md`](best-practice-reference-matrix.md)

## 官方参考

- AMD/Xilinx: `UG899 Vivado Design Suite User Guide: I/O and Clock Planning`
- Intel 各 family 的 bank / IO standard / package planning 手册
