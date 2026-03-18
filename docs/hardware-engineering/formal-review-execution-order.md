# 正式硬件评审执行顺序

## 目的

这一页不是重复 15 篇核心文档的正文，而是规定正式硬件评审时应该按什么顺序使用它们。

如果顺序错了，评审常见问题是：

- 一开始就钻进局部器件细节，漏掉系统级硬错误
- 高速和模拟问题被提前讨论，但电源树本身还没成立
- 布局问题和制造问题混在一起，结论无法落地
- bring-up 阶段才发现前面没有形成明确的放行门槛

## 适用场景

适用于：

- 新板原理图正式评审
- layout 前联合评审
- 打样前冻结前评审
- bring-up 前风险收敛评审

## 不适用场景

不适用于单一器件的局部替换 review，或者已经进入实验室故障定位后的局部问题分析。

## 评审总顺序

正式评审建议固定为 6 段：

1. 系统供电与保护
2. 板外接口与总线
3. FPGA / DDR / 高速链路
4. 模拟、采样与热
5. 制造与工艺
6. bring-up 放行条件

这个顺序的原则是：

- 先看会直接烧板、错 rail、错时序的问题
- 再看接口、电平、链路和高频约束
- 最后才看制造和 bring-up 交付

## Phase 1: 系统供电与保护

先看：

- [`power-tree-review-checklist.md`](power-tree-review-checklist.md)
- [`buck-converter-schematic-review.md`](buck-converter-schematic-review.md)
- [`tvs-and-esd-placement.md`](tvs-and-esd-placement.md)

通过标准：

- 所有 rail 都能回答来源、负载、容差、最大电流、启动约束
- 关键 DC/DC 没有明显功率环路和反馈错误
- 所有板外入口的保护位置和回流路径说得清楚

不通过时不要继续：

- 电源树没定，高速和模拟讨论大多会失真

## Phase 2: 板外接口与总线

再看：

- [`i2c-pullup-and-topology.md`](i2c-pullup-and-topology.md)
- [`usb2-protection-and-routing.md`](usb2-protection-and-routing.md)
- [`ethernet-phy-bringup-checklist.md`](ethernet-phy-bringup-checklist.md)

通过标准：

- 总线电平域和拓扑无硬冲突
- USB 入口保护、`VBUS`、`CC`、`D+/D-` 策略闭环
- PHY 时钟、strap、`MDIO`、磁性件和 RGMII 延迟策略明确

## Phase 3: FPGA / DDR / 高速链路

接着看：

- [`fpga-power-rail-planning.md`](fpga-power-rail-planning.md)
- [`fpga-bank-voltage-planning.md`](fpga-bank-voltage-planning.md)
- [`ddr-layout-review-checklist.md`](ddr-layout-review-checklist.md)
- [`differential-pair-routing.md`](differential-pair-routing.md)

通过标准：

- FPGA rail 和 bank 规划没有后期必返工风险
- DDR 拓扑、分组和关键约束已明确
- 差分对约束来源、返回路径和过孔策略可落地

不通过时不要进入 layout 冻结：

- 这类问题一旦带到 PCB，代价通常最高

## Phase 4: 模拟、采样与热

然后看：

- [`mixed-signal-grounding.md`](mixed-signal-grounding.md)
- [`adc-reference-and-input-drive.md`](adc-reference-and-input-drive.md)
- [`thermal-via-and-copper-spreading.md`](thermal-via-and-copper-spreading.md)

通过标准：

- 模拟回流路径和数字回流关系清楚
- ADC 参考、驱动和 RC 网络有明确依据
- 热路径和热过孔策略同时满足电气与工艺要求

## Phase 5: 制造与工艺

然后看：

- [`manufacturing-dfm-quick-check.md`](manufacturing-dfm-quick-check.md)

通过标准：

- 高风险封装、热焊盘、测试可达性、拼板和返修空间都有明确结论
- 电气成立但工艺不可控的问题已经被提前拦住

## Phase 6: Bring-up 放行条件

最后看：

- [`power-up-debug-sequence.md`](power-up-debug-sequence.md)

通过标准：

- 首电顺序、限流、通过条件、观测点和最小闭环都明确
- 板子到实验室后不会处于“只能盲试”的状态

## 最小评审输出

一次像样的正式评审，至少要产出：

- 阻塞问题列表
- 可接受风险列表
- 必须在 layout 前关闭的问题
- 必须在打样前关闭的问题
- bring-up 前必须准备的观测点和工装

## 常见错误顺序

- 先看 DDR 走线，后看 rail 规划
- 先抓 USB 枚举，后看入口保护和 `VBUS`
- 先谈 ADC 精度，后看混合地和参考源
- 先看功能，后看 DFM

这些顺序都会让评审结果失焦。

## 建议用法

- 开正式评审时，把这页当 agenda。
- 每个阶段只引用对应文档，不把 15 篇一次性展开。
- 一个阶段没过，就不要跳到下一个阶段装作继续推进。
