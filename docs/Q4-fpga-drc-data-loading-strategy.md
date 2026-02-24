# Q4: FPGA 原理图 DRC — Datasheet 解析数据的最优加载策略

## 背景

我们正在构建一个 **LLM 驱动的原理图审核系统**，核心流程：

```
输入: 网表(netlist) + BOM + Datasheet 解析数据(JSON)
输出: DRC 报告 (错误/警告/建议)
```

### 已完成的数据层

我们已经为 FPGA (Xilinx/AMD XCKU3P) 构建了 **5 层 pin 定义 JSON**：

| Layer | 内容 | 数据量 (FFVB676) |
|-------|------|------------------|
| L1 | Physical Pin Map (pin↔name, bank, io_type) | 676 pins |
| L2 | Pin Classification + Mandatory Connection Rules | 17 CONFIG + 6 SPECIAL, 每个带 DRC 规则 |
| L3 | Bank Structure (HP/HD/GTY, VCCO 范围, VREF/Clock capable) | 12 banks |
| L4 | Differential Pair Map (IO + GT) | 172 对 (132 IO + 16 GT_RX + 16 GT_TX + 8 REFCLK) |
| L5 | DRC Rule Templates | 8 条规则 |

**单个封装的完整 JSON 约 194KB (~50K tokens)**，显然不能一次性全部灌给 LLM。

### 同时还有普通 IC 的 datasheet 解析数据

除了 FPGA，BOM 中还有大量普通 IC（LDO、Buck、运放、接口芯片等），每个器件也有 datasheet 解析出的：
- 电气参数 (Vin_max, Iout_max, etc.)
- Pin 定义 (pin_number → pin_name → function)
- 绝对最大额定值
- 推荐工作条件

## 核心问题

**在 LLM 驱动的原理图 DRC 流程中，datasheet 解析数据应该如何加载给 LLM？**

### 具体争议点

#### 方案 A: MCP Tool 查询接口

LLM 通过 tool call 按需查询，不预加载数据：

```python
# LLM 调用示例
query_pin(device="XCKU3P", package="FFVB676", pin="AF1")
→ {"pin": "AF1", "name": "MGTYRXN0_224", "function": "GT_RX", "bank": "224", ...}

query_bank(device="XCKU3P", package="FFVB676", bank="64")
→ {"io_type": "HP", "supported_vcco": [1.0,1.2,1.35,1.5,1.8], ...}

check_power_integrity(device="XCKU3P", package="FFVB676", connected_pins=[...])
→ {"missing_vcc": [...], "missing_gnd": [...]}
```

优点：Token 效率高，可扩展
缺点：多轮 tool call 增加延迟，LLM 可能遗漏该查的东西，依赖 LLM 的查询策略

#### 方案 B: 分阶段 Prompt 注入

按检查任务分批把数据注入 prompt：

```
阶段 1 — 全局概览 (~2KB): summary + power_rails + drc_rules
阶段 2 — CONFIG 检查 (~3KB): 仅 CONFIG pins + 网表对应连接
阶段 3 — 电源检查 (~5KB): 仅 POWER/GND pins + 电源网络
阶段 4 — 按 Bank 检查 IO (每次 ~3KB): 单 bank IO + diff_pairs
阶段 5 — GT 检查 (~4KB): GT pins + diff_pairs + REFCLK
```

优点：每阶段数据完整，LLM 不会遗漏
缺点：流程硬编码，跨阶段问题难发现

#### 方案 C: 混合方案

预加载精简骨架（summary + banks + drc_rules + config_pins），详细数据按需查询。

#### 方案 D: 代码预处理 + LLM 仅做判断

用确定性代码（Python）完成所有可编程的检查（电源完整性、pin 连接性、VCCO 一致性），只把代码无法判断的问题（设计意图、信号完整性、布局建议）交给 LLM。

### 需要考虑的约束

1. **器件多样性**: 一个原理图可能有 1 个 FPGA + 20~50 个普通 IC，数据格式和检查逻辑不同
2. **网表规模**: 典型 FPGA 设计网表可能有数千个 net
3. **Token 预算**: 单次 LLM 调用的 context window 有限（128K~200K tokens）
4. **准确性要求**: 硬件 DRC 容错率为零，漏检比误报严重得多
5. **可维护性**: 新器件加入时的适配成本
6. **实时性**: 工程师期望分钟级出结果，不是小时级

### 更深层的问题

1. **LLM 在这个流程中的角色边界在哪？** 哪些检查应该是确定性代码，哪些才需要 LLM 的"理解能力"？
2. **数据粒度**: 给 LLM 看 pin 级别的原始数据，还是预处理成 "Bank 64 有 3 个 IO 标准冲突" 这样的摘要？
3. **多器件交叉检查**: 比如 FPGA Bank 64 的 VCCO 是 1.8V，连接到它的 LDO 输出是否确实是 1.8V？这种跨器件检查如何组织数据？
4. **增量检查 vs 全量检查**: 工程师改了一个 net，是重跑全部还是只检查受影响的部分？

## 期望回答

1. 推荐的整体架构（方案 A/B/C/D 或其他）
2. LLM vs 确定性代码的职责划分
3. 数据加载的具体策略（什么时候加载什么数据，粒度如何）
4. 多器件交叉检查的数据组织方式
5. 如果选 MCP Tool 方案，Tool 接口应该怎么设计（粒度、返回格式）

---

## 超级 LLM 回答

*(预留区域 — 请将回答粘贴到此处)*



