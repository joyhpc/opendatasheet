# DDR 布局评审清单

## 适用场景

适用于：

- SoC / FPGA 到 DDR3 / DDR4 / DDR5 的板级走线评审
- 原理图后期到布局前的约束复核
- post-layout 的 SI/PI 联合检查

## 不适用场景

不适用于只看控制器寄存器配置或 training 软件问题。本文讨论的是板级拓扑、长度、回流和布线质量。

## 典型失效症状

DDR 板级问题常见表现是：

- training 偶发通过、偶发失败
- 某些温度、某些频率、某些 DIMM / 器件组合才出错
- 读写错误集中在某个 byte lane
- 某些板子稳定，批量一致性差
- 电源和时钟看似都对，但数据裕量很差

## 先看什么

不要先盯“等长”数字。先看：

1. 拓扑是否选对。
2. byte lane / DQS / clock / address-command 是否被分组管理。
3. 返回路径是否连续。
4. 过孔 stub 和层切换是否可控。

## 必查顺序

### 1. 拓扑

- Fly-by、T-branch、点对点是否与控制器和代际要求一致。
- DIMM、离散颗粒、PoP 的规则是否被混用。
- 终端方案、ODT 策略是否与拓扑匹配。

### 2. 分组

- 时钟对、地址命令、控制、DQ、DQS、DM/DBI 是否按不同规则集处理。
- byte lane 是否完整，不混交，不跨不必要区域。
- 原理图网络命名和 layout 约束是否一一对应。

### 3. 长度与回流

- 长度匹配是否符合控制器和器件手册，而不是只按经验值。
- 参考平面是否连续。
- 是否存在跨分割、长开槽、参考切换不连续的问题。

### 4. 过孔与细节

- 关键网络是否控制了过孔 stub，必要时是否回钻。
- 时钟和 DQS 对是否避免不对称层切换。
- 终端、电源去耦和 DRAM 摆位是否服务于拓扑，而不是只服务器件摆放美观。

## 硬规则

- DDR 不能只看“等长”，必须同时看拓扑、分组、回流和过孔。
- 时钟、DQS、DQ、地址命令不是同一规则集。
- 原理图如果没有清晰分组，layout 阶段几乎必然出错。
- 如果没有仿真结果，就必须更保守地遵守器件与控制器手册的默认约束。
- 频率越高，回流和过孔问题通常比肉眼看到的线长问题更早爆炸。

## 常见失误

- 只追求线长匹配，忽略返回路径和过孔 stub。
- 多个 byte lane 混交，bring-up 难以定位。
- 原理图没有明确 lane / strobe 分组，layout 只能人工猜。
- 以为样板能 train 就说明布局没问题。

## 评审示例

例子：

- DDR4 设计通过了初步 training
- 但 byte lane 之间有交叉换层
- DQS 对和部分 DQ 共享了不理想的返回路径
- 地址命令与时钟只看了“长度差不多”

正式 review 时，合理结论应是：

- `WARNING`: training 通过不等于布局正确，仍需看 lane 分组与回流质量。
- `ERROR`: 若 DQS / DQ 关键组跨越不连续参考区，不应放行。
- `WARNING`: 只按“差不多等长”处理地址命令与时钟，不足以支撑高频设计。

DDR review 的目标不是“先跑起来”，而是减少边界条件和量产一致性风险。

## 仓库入口

- 硬件文档总入口：[`index.md`](index.md)
- 相关高速主题：[`differential-pair-routing.md`](differential-pair-routing.md)
- 来源矩阵：[`best-practice-reference-matrix.md`](best-practice-reference-matrix.md)

## 官方参考

- Intel: [`Guidelines: Board Design Requirement for DDR2, DDR3, and LPDDR2`](https://www.intel.com/content/www/us/en/docs/programmable/683572/current/guidelines-board-design-requirement.html)
- Intel: [`DDR4 Board Design Guidelines`](https://www.intel.com/content/www/us/en/docs/programmable/683216/22-2-2-6-1/ddr4-board-design-guidelines.html)
- Intel: [`DDR5 Board Design Guidelines`](https://www.intel.com/content/www/us/en/docs/programmable/772538/25-1/ddr5-board-design-guidelines.html)
