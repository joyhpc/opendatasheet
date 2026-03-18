# 电源树评审清单

## 适用场景

适用于：

- 新板原理图正式评审
- FPGA / SoC / DDR / SerDes 板卡的 rail 规划复核
- bring-up 前的电源结构预检查
- 多电源域系统的量产风险审查

## 不适用场景

不适用于只想快速确认“某个 LDO 外围值对不对”的局部问题。那类问题应单独看具体电源拓扑文档，而不是把整棵电源树一起拖进来。

## 典型失效症状

如果电源树设计有结构性问题，现场通常会表现为：

- 首次上电电流异常大，限流立刻打满
- 某些 rail 电压正确，但系统仍不启动
- 上电顺序偶发成功，复现不稳定
- FPGA / DDR / PHY 等器件在高负载或热态下随机失效
- 掉电时出现反向灌电、残余供电或异常发热

## 先看什么

电源树 review 不要按页翻图，要按下面顺序走：

1. 画出输入源到末端负载的树状关系。
2. 标清每条 rail 的 `Vin`、`Vout`、`Imax`、容差、启动约束、保护链路。
3. 识别噪声敏感 rail：核心电源、模拟基准、时钟、PLL、DDR VREF/VTT、收发器模拟电源。
4. 识别顺序敏感 rail：PMIC、FPGA、DDR、PHY、热插拔、电池路径。
5. 最后才看单个 regulator 的外围细节。

## 必查顺序

### 1. 输入层

- 输入是否有反接、浪涌、ESD、热插拔、限流或保险策略。
- 输入最差电压范围是否被所有后级覆盖。
- 线缆、连接器、背板或车载输入是否定义了最坏瞬态。

### 2. 分配层

- 每个中间 rail 是否明确服务哪些负载。
- 是否存在把模拟、数字、高 di/dt 负载无差别挂到同一中间 rail 的情况。
- 中间 rail 掉压时，下游是否会通过 IO、反馈、ESD 结构反灌。

### 3. 末端稳压层

- 每个 regulator 的输入范围、启动阈值、掉压、限流、热行为是否覆盖最差工况。
- enable、PG、fault、soft-start 是否真的参与了系统控制，而不是“留着没用”。
- 同一 rail 是否被多个器件假设为“总会最先稳定”。

### 4. 负载层

- FPGA、DDR、ADC、时钟、PHY 是否拿到了合适噪声等级的电源。
- 大电流 rail 的返回路径、铜皮、电流采样和测试点是否清楚。
- 关键 rail 是否有 bulk + 高频去耦的分层策略。

## 硬规则

- 每一条 rail 都必须能回答这五个问题：谁供电、给谁用、最大多大电流、上电何时稳定、失败时如何保护。
- 不允许把 `能从同一个母线分出来` 当成 `适合共用同一 regulator`。
- FPGA 核心、DDR 参考、时钟/PLL、模拟基准必须单独审视，不能被平均处理。
- 如果某个负载依赖另一条 rail 的先后顺序，原理图里必须看得出这个约束来自哪里。
- 如果掉电可能反灌，就必须在原理图层面看到阻断或钳制策略。

## 常见失误

- 只看稳压器额定输出电流，不看最差输入电压和热耗散。
- 只在 PPT 上写“模拟电源”和“数字电源”分开，原理图里实际上共用同一脏 rail。
- 把 PMIC/PG/EN 全连上了，但没有形成真实的顺序控制。
- 把 FPGA、DDR、SerDes 的 rail 规划推迟到 layout 或 bring-up 阶段。

## 评审示例

例子：

- 输入 12 V
- 先降到 5 V
- 再从 5 V 分出 FPGA 1.0 V 核心、3.3 V IO、2.5 V DDR 相关 rail
- 同时把 ADC 参考和时钟缓冲也挂在 5 V 派生的同一颗 LDO 上

正式 review 时，应该立刻给出三个结论：

- `WARNING`: ADC 参考和时钟缓冲不应只因电流小就共用同一“方便的” 5 V 后级 LDO，需要重新看噪声隔离。
- `ERROR`: 若 FPGA 核心和 DDR rail 的启动先后依赖 PMIC / PG，而图上看不出控制链，不能放行。
- `WARNING`: 如果 12 V 入口没有明确浪涌和反接策略，后级所有 rail 都建立在不稳输入上。

这个例子的重点不是具体电压值，而是：电源树 review 要先抓结构性问题，而不是先争某颗 10 uF 电容值。

## 仓库入口

- 硬件文档总入口：[`index.md`](index.md)
- 来源矩阵：[`best-practice-reference-matrix.md`](best-practice-reference-matrix.md)
- 相关主题：[`buck-converter-schematic-review.md`](buck-converter-schematic-review.md)

## 官方参考

- ADI: [`MT-101 Decoupling Techniques`](https://www.analog.com/media/en/training-seminars/tutorials/mt-101.pdf)
- ADI: [`MT-093 Thermal Design Basics`](https://www.analog.com/media/en/training-seminars/tutorials/MT-093.pdf)
- Intel: [`PCB Design Guidelines: Agilex 5`](https://www.intel.com/content/www/us/en/docs/programmable/821801/current/power-distribution-network-design-guidelines-01408.html)
