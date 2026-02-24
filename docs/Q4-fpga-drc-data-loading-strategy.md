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

这是一个极其经典的**“特定领域大模型应用（Domain-Specific LLM Application）”**与**“EDA 软件架构设计”**的交叉问题。

在硬件原理图 DRC 领域，最大的紧箍咒是**“容错率为零，漏报比误报更致命”**。大模型（LLM）由于固有的“长上下文注意力丢失（Lost in the middle）”、“幻觉”以及“缺乏严格图遍历能力”的缺陷，**绝对不能直接用来做海量引脚的连通性比对和查表**。将 194KB 的 JSON 和数千个 Net 喂给大模型，必然导致严重的漏判（例如悄悄忽略某个 VCCO 的电压约束，导致板子烧毁）。

因此，强烈推荐采用 **方案 D 为核心控制流，辅以方案 C（骨架预加载）与方案 A（高阶语义 Tool）的“神经符号（Neuro-Symbolic）混合架构”**。我们也可称之为**“代码主导的图引擎 + LLM 专家副驾”**。

以下是对您问题的深度拆解与系统设计方案：

---

### 一、 整体架构推荐：代码图计算基座 + LLM 专家系统

将您的 5 层 JSON 和网表视为“数据库”，Python 视为“确定性执行引擎”，LLM 视为“主任审查工程师”。

1. **图谱构建 (Graph Builder - Python)**：解析 Netlist、BOM、所有 Datasheet JSON，在内存中构建一张**多属性有向拓扑图 (Property Graph)**（节点为 器件/Pin/Net，属性为 电压、IO Type、最大电流等）。
2. **确定性预检 (Rule Engine - Python)**：运行图遍历算法，跑完 100% 的硬性规则检查（电压传递比对、悬空检查等），生成一份“粗筛体检报告”。
3. **LLM 语义研判 (Agent Reviewer - LLM)**：将代码找出的明确违规（Violations）和高度凝练的局部网络拓扑（Sub-graphs）组装成 Prompt 发给 LLM。LLM 负责过滤误报、核随意图、出具具有人类工程师专业度的修改建议。

---

### 二、 职责边界：LLM vs 确定性代码

**核心准则：凡是能用 `if-else`、数学不等式或图遍历表达的规则，全部交给代码。LLM 只做“语义”、“经验”和“意图”理解。**

| 检查维度 | 确定性代码职责（0漏判要求，跑通前4层JSON） | LLM 职责（高级理解与推理，跑第5层规则） |
| --- | --- | --- |
| **连通性与拓扑** | - 查必连管脚（L2）是否悬空<br>

<br>- 查差分对 P/N（L4）是否等长/接反同 Bank<br>

<br>- 查 Output 是否与其他 Output 短接 | - 结合网表命名（如 `I2C_SDA` 或 `PHY_RST_N`）判断普通的 Open-Drain 是否遗漏上拉，或者低有效信号是否被错误下拉。<br>

<br>- 评估某管脚悬空是否符合特定的配置意图。 |
| **多器件电气匹配** | - **网络电压推导**：基于图算法从 LDO 输出推导整个 Net 的实际电压。<br>

<br>- **属性碰撞**：查 Net 电压是否落在 FPGA Bank VCCO（L3）合法区间，是否超过普通 IC 的 $V_{in\_max}$。 | - 评估退耦电容网络（0.1uF/10uF 组合）是否符合该接口速率下电源完整性（PI）的经验布局准则。<br>

<br>- 诊断电压冲突根因（如反馈电阻配错）并给出改板建议。 |
| **非结构化数据** | - 执行 Layer 5 中已结构化的逻辑。 | - 阅读 Datasheet 中未结构化的自然语言 Note（如：“若不使用 GTY，需通过 10k 电阻接地”），结合拓扑判断是否合规。 |

---

### 三、 多器件交叉检查的数据组织方式（解决信息孤岛）

多个普通 IC 和 FPGA 之间的互相连接是 DRC 的难点。底层必须以 **网络 (Net) 和 信号流** 为中心重组数据，而不是以器件为中心。绝对不要让 LLM 自己去分别查 LDO 和 FPGA 的 JSON 然后做对比。

**采用“Source -> Net -> Sink (驱动 -> 网络 -> 负载)” 数据模型：**

当 Python 图引擎在处理网表发现异常，或者需要 LLM 审查某个核心链路时，应动态生成如下 JSON 切片喂给 LLM：

```json
{
  "net_name": "VCC_1V8_FPGA",
  "inferred_net_state": {"voltage": 1.8, "type": "POWER"},
  "source": {
    "device": "U2 (TPS7A85 LDO)", "pin": "VOUT", 
    "datasheet_limits": {"V_out_max": 1.8, "I_max": "4A"}
  },
  "sinks": [
    {
      "device": "U1 (XCKU3P)", "pin_group": "Bank 64 VCCO (4 pins)", 
      "datasheet_req": {"VCCO_allowed": [1.2, 1.35, 1.5, 1.8]},
      "current_io_standards": ["LVDS", "LVCMOS18"]
    },
    {
      "device": "U3 (SPI Flash)", "pin": "VCC", 
      "datasheet_req": {"VCC_allowed": [1.65, 1.95]}
    }
  ],
  "passives": [{"type": "Capacitor", "value": "10uF", "qty": 4}]
}

```

*注：一旦将这种“链路高度聚合结构”发给 LLM，LLM 能立刻一眼完成跨器件的语义研判（1.8V 完美兼容 FPGA 和 Flash，且有 4 个旁路电容）。如果依赖 LLM 自己去按需查询，很容易丢失上下文导致漏判。*

---

### 四、 数据加载的具体策略（何时给什么，粒度如何）

采用**“骨架预加载 + 异常切片按需注入”**的策略：

1. **阶段 1：全局 Context 注入（预加载，约 2~3K Tokens）**
在 System Prompt 中加载最高层面的单板摘要，让 LLM 建立全局认知：
> *"当前设计：1 个 XCKU3P, 2 个 TPS7A LDO。供电树推导结果：VCCINT=0.85V, VCCO_64=1.8V。底层代码引擎已发现 3 个 Hard Error 和 5 个 Warning，请逐一审查..."*


2. **阶段 2：异常切片组装（按需 Prompt 注入，每次 ~2K Tokens）**
当代码引擎发现 VCCO 冲突时，不要发全量的 Bank 数据，只发包含违例的微观上下文（即上述的 Source-Net-Sink 结构）：
> *"【DRC告警_01】代码预检发现 U1 Bank 64 存在电压冲突。上下文如下 JSON... 请给出修复建议。"*


3. **阶段 3：接口级模块化注入（审查设计意图）**
对于需要验证语义的模块，按“接口链路”提取拓扑发给 LLM。例如提取所有带有 `PCIE_` 前缀的网表及相关的 L4 GT Pin 摘要，发给 LLM 审查交流耦合电容是否放置正确。

---

### 五、 MCP Tool 接口设计规范

既然主力遍历和查表已经交给了 Python 代码，MCP Tool 的定位就变成了 LLM 的 **“深水区探针”**。
**极其重要：绝不能设计 `query_pin(pin="AF1")` 这种像素级接口**，它会极其浪费 Token，导致长延迟，且让 LLM 陷入“只见树木不见森林”的死循环。

推荐的 4 个高阶业务级 Tool 接口设计：

1. **`trace_net_topology(net_name: str)`**
* **返回格式**：上述的 Source-Net-Sink 聚合拓扑数据块（包含沿途的串/并联阻容）。
* **适用场景**：LLM 怀疑某根复位线或 I2C 线上拉有问题时，一键调取全链路图景。


2. **`get_bank_macro_status(device: str, bank_id: str)`**
* **返回格式**：`{"bank": 64, "VCCO": "1.8V", "used_io_count": 12, "connected_nets": ["I2C_SDA", "SPI_CLK"...]}`。
* **适用场景**：用于 LLM 快速判断 Bank 内部是否存在高速信号与慢速敏感信号混用的串扰风险。


3. **`query_datasheet_guidelines(device_model: str, feature_keyword: str)`**
* **返回格式**：RAG 检索出的原厂自然语言段落。
* **适用场景**：遇到特定芯片（如 LDO），LLM 调用以检索“Layout 建议”或“上电时序要求”。


4. **`get_pin_mux_options(device: str, pin_name: str)`**
* **返回格式**：该管脚的所有复用功能列表。
* **适用场景**：判断用户将某个管脚接地的真实意图（是否为了屏蔽某个特定的 Alternate Function）。



---

### 六、 增量检查 vs 全量检查策略（实现分钟级响应）

工程师期望的**“分钟级出结果”**，正是这种混合架构的巨大优势：

1. **确定性基座（Python 代码）：永远跑全量（毫秒级）。**
在 Python 中加载几千个 Net 建图并做几万次电压和连接比对，只需几百毫秒。全量重跑能彻底杜绝因“修改一处导致另一处级联报错”的漏报。
2. **LLM 语义诊断：只跑增量（秒级）。**
对比前后两次 Python 引擎跑出的《DRC 粗筛报告》和《网络拓扑图 Hash》。
* 如果工程师修改了外部传感器的反馈电阻，Python 会秒出新的报错列表。
* 系统在后台做 Diff，**仅将受该电阻影响的局部子图（Blast Radius）提取出来**。
* 生成 Prompt：*"用户将 R12 的阻值从 10K 改为 4.7K，当前该网络拓扑如下，请重新评估电气安全性。"*
* LLM 只需对这一个局部变更进行意图评估，几秒钟到十几秒即可返回精确结果。



### 总结

您构建的 5 层 JSON 是极其高质量的**“机读规则库”**，它们应该被 100% 消化在 Python 的图数据库中。让确定性代码去做繁重的“对连线、查手册、比电压”工作以确保 0 漏检；让 LLM 拿着代码出具的“化验单”和“链路拓扑切片”去做高级专家诊断。这是兼顾准确度、扩展性与实时响应的最佳工程实践。



