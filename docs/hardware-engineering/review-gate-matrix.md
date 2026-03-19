# 硬件评审放行门槛矩阵

## 目的

这页不是替代 15 篇核心文档，而是把正式评审里最关键的“什么情况下绝不放行”压缩成一页。

如果一场 review 结束后，只剩下“大家感觉问题不大”，没有明确阻塞条件和最小证据，那就不算完成评审。

建议和 [`formal-review-execution-order.md`](formal-review-execution-order.md) 以及 [`review-record-template.md`](review-record-template.md) 一起使用。

## 使用方式

- 每个 phase 至少过一遍这页，再展开看对应正文。
- 命中任一“阻塞条件”，就不要进入下一个 phase。
- “最小证据”不是可选项；没有图、没有表、没有测量计划，结论就不成立。
- 如果问题可以接受带风险前进，必须在 [`review-record-template.md`](review-record-template.md) 里写清责任人和关闭阶段。

## Phase 1: 系统供电与保护

### [`power-tree-review-checklist.md`](power-tree-review-checklist.md)

- 阻塞条件：任一关键 rail 的来源、负载、最大电流、容差或启动约束说不清；掉电反灌路径未闭环。
- 最小证据：电源树总图、rail 电流预算表、关键 `EN/PG` 控制链截图。
- 放行信号：所有关键 rail 都能回答“谁供电、给谁用、什么时候稳定、失败时怎么保护”。

### [`buck-converter-schematic-review.md`](buck-converter-schematic-review.md)

- 阻塞条件：反馈分压、补偿、功率环路、大电流输入输出回路任一项没有依据；最差输入和热边界没算过。
- 最小证据：`Vin/Vout/Iout/f_sw` 表、关键外围取值依据、功率环路与回流路径截图。
- 放行信号：稳压器在最差输入、电流、温升条件下仍有清楚余量。

### [`tvs-and-esd-placement.md`](tvs-and-esd-placement.md)

- 阻塞条件：保护件不在入口、回流路径不短直、器件电容或钳位等级与被保护接口冲突。
- 最小证据：连接器附近布局截图、保护器件选型表、保护地回流说明。
- 放行信号：能明确说明瞬态先经过谁、在哪里泄放、为什么不会先打到主芯片。

## Phase 2: 板外接口与总线

### [`i2c-pullup-and-topology.md`](i2c-pullup-and-topology.md)

- 阻塞条件：不同电压域直接硬连；上拉重复叠加后阻值失控；总线电容和速度目标不匹配。
- 最小证据：I2C 拓扑图、`Rp` 取值与总线速度依据、电平转换策略说明。
- 放行信号：总线拓扑、电平域和时序预算三者一致，没有靠“实验室试一下”兜底。

### [`usb2-protection-and-routing.md`](usb2-protection-and-routing.md)

- 阻塞条件：Type-C 未定义 `CC`；`VBUS` 方向和保护策略不成立；`D+/D-` 上存在长 stub、高电容或错误保护位置。
- 最小证据：连接器页原理图、连接器附近布局截图、`VBUS/CC/D+/D-` 角色定义说明。
- 放行信号：插拔、浪涌、枚举路径在图和布局上都闭环，不依赖侥幸线缆兼容性。

### [`ethernet-phy-bringup-checklist.md`](ethernet-phy-bringup-checklist.md)

- 阻塞条件：PHY 供电、复位、时钟、strap、`MDIO`、磁性件或 RGMII 延迟策略任一项模糊。
- 最小证据：strap 表、时钟来源说明、PHY 到磁性件 / RJ45 拓扑截图。
- 放行信号：上电后 PHY 至少具备稳定识别、读写寄存器、建立链路的基础条件。

## Phase 3: FPGA / DDR / 高速链路

### [`fpga-power-rail-planning.md`](fpga-power-rail-planning.md)

- 阻塞条件：核心、辅助、收发器、PLL、配置相关 rail 缺失；电流预算或上电顺序不成立。
- 最小证据：器件 rail 清单、各 rail 电流预算、上电顺序或 PMIC 控制链说明。
- 放行信号：不会在 bring-up 或换封装阶段才发现 rail 不够、顺序不对、去耦级别不够。

### [`fpga-bank-voltage-planning.md`](fpga-bank-voltage-planning.md)

- 阻塞条件：同 bank 混入不兼容 IO 标准；`Vcco/Vref` 规划和接口要求冲突；未来接口扩展没有余量。
- 最小证据：bank 对照表、每组 IO standard / `Vcco` / `Vref` 映射、约束来源说明。
- 放行信号：bank 电压规划与管脚复用已经收敛，不会因为一个外设接口返工整片 bank。

### [`ddr-layout-review-checklist.md`](ddr-layout-review-checklist.md)

- 阻塞条件：拓扑、分组、端接、`VREF/VTT`、字节通道或长度约束没有收敛。
- 最小证据：DDR 拓扑图、byte lane 分组表、关键匹配规则与参考层策略。
- 放行信号：layout 团队已经拿到可执行的分组和约束，而不是模糊口头要求。

### [`differential-pair-routing.md`](differential-pair-routing.md)

- 阻塞条件：差分阻抗来源不明；返回路径中断；跨层换参考时没有回流过渡策略。
- 最小证据：叠层阻抗表、关键差分链路约束、跨层与连接器过渡说明。
- 放行信号：差分对约束来自明确链路要求，而不是经验值拼凑。

## Phase 4: 模拟、采样与热

### [`mixed-signal-grounding.md`](mixed-signal-grounding.md)

- 阻塞条件：把“分地”当结论但没有回流分析；敏感模拟回路与高 `di/dt` 数字回流抢同一路径。
- 最小证据：关键回流路径草图、模数边界说明、敏感器件附近平面策略截图。
- 放行信号：可以明确回答每条关键模拟电流和数字回流怎么走、为什么不会互相污染。

### [`adc-reference-and-input-drive.md`](adc-reference-and-input-drive.md)

- 阻塞条件：ADC 参考源驱动能力、输入源阻抗、采样充电路径或 RC 取值没有依据。
- 最小证据：参考源与输入驱动原理图、采样 RC 计算或数据手册依据、关键时序预算。
- 放行信号：ADC 精度预算建立在真实驱动和稳定参考上，不是靠平均值想象。

### [`thermal-via-and-copper-spreading.md`](thermal-via-and-copper-spreading.md)

- 阻塞条件：高耗散器件没有连续热路径；热过孔策略与制造能力冲突；热焊盘和铜扩展无法兼顾焊接可靠性。
- 最小证据：热点器件清单、热路径说明、热过孔与铜皮策略截图。
- 放行信号：电、热、工艺三方面没有互相打架，量产时不会因为散热改动推翻布局。

## Phase 5: 制造与工艺

### [`manufacturing-dfm-quick-check.md`](manufacturing-dfm-quick-check.md)

- 阻塞条件：关键封装没有可制造性确认；测试点、返修空间、拼板边界或特殊工艺要求未收敛。
- 最小证据：高风险封装清单、测试可达性说明、制造约束或板厂注意事项。
- 放行信号：不是“电气上能工作”，而是“工厂能稳定做出来、实验室能稳定测起来”。

## Phase 6: Bring-up 放行条件

### [`power-up-debug-sequence.md`](power-up-debug-sequence.md)

- 阻塞条件：首电顺序、限流阈值、关键观测点、通过条件或最小功能闭环没有定义。
- 最小证据：bring-up 执行清单、首电观测点表、必要工装和示波器触发计划。
- 放行信号：新板到实验室后，工程师能按固定步骤排查，而不是靠盲插、盲测、盲试。

## 使用纪律

- 评审会上如果有人说“这个先不管，后面调起来再看”，默认按风险项甚至阻塞项处理。
- 没有证据链的“经验判断”不能替代放行门槛。
- 任何跨 phase 的阻塞问题，都要回到最早相关 phase 关闭，不能挂在最后统一处理。
