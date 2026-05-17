# Q3: 原理图审核知识库的 Pin 定义 Schema 设计

> Historical schema design note. This page may discuss ideas that differ from the checked-in `device-knowledge/2.0` export contract. For current facts, read [`current-state.md`](current-state.md), [`schema-v2-domains-guide.md`](schema-v2-domains-guide.md), and the relevant schema/export code first.

## 问题

我在构建一个"原理图自动审核工具"的知识库。需要从电子元器件 datasheet 中提取 pin 定义信息，存储为结构化 JSON，供审核引擎使用。

审核引擎需要回答的典型问题：
1. 某个 pin 是输入还是输出？电源还是信号？
2. 某个 pin 的电压/电流绝对最大值是多少？
3. 两个 pin 之间是否可以直连？（电平兼容性）
4. 某个 pin 是否需要上拉/下拉电阻？
5. 未使用的 pin 应该如何处理？（悬空/接地/接电源）
6. 多封装变体时，同一功能 pin 在不同封装中的编号映射

当前我的 pin 定义 schema 很简单：
```json
{
  "pin_number": "string or number",
  "pin_name": "string",
  "type": "string (Input/Output/Power/I/O)",
  "description": "string"
}
```

这对于原理图审核来说信息不够。请设计一个更完善的 pin 定义 JSON schema，要求：
1. 能支持上述所有审核场景
2. 能处理多封装变体（同一芯片 SOT-23 和 DFN 封装 pin 不同）
3. 能关联到 electrical_characteristics 中的参数（如某 pin 的 max voltage）
4. 能表达 pin 之间的关系（如差分对、互补输出）
5. 保持 schema 简洁，不过度设计
6. 给出 3-5 个不同类型器件的示例（LDO、OpAmp、数字开关、MCU）

---

## 答案

为了构建一个真正有用的“原理图自动审核（ERC/DRC）引擎”，我们需要将当前的 Schema 设计思路从**“以物理引脚号为中心（Physical Pin Centric）”**彻底重构为**“以逻辑功能引脚为中心（Logical Pin Centric）”**。

这意味着，引擎在底层解耦了物理封装与电气规则。以下是兼顾全面性与简洁性的进阶版 JSON Schema 设计，以及配套的业务解析逻辑和真实器件示例。

### 一、 完善后的 Pin 定义 JSON Schema

为满足你的需求，我在 Schema 中引入了 **多封装字典映射** 和 **电气属性公式化（Expression）** 的核心设计：

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Component Pin Definition for Schematic Auditing",
  "type": "object",
  "properties": {
    "part_number": { "type": "string", "description": "器件型号，如 STM32G030" },
    "logical_pins": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string", "description": "逻辑引脚名，如 EN, PA0, IN+" },
          "description": { "type": "string" },
          
          "packages": {
            "type": "object",
            "description": "【核心】封装映射。Key为封装名，Value为物理引脚号数组（支持多引脚并联如多个GND）",
            "additionalProperties": {
              "type": "array",
              "items": { "type": ["string", "integer"] }
            }
          },
          
          "direction": {
            "type": "string",
            "enum": ["INPUT", "OUTPUT", "BIDIRECTIONAL", "PASSIVE", "POWER_IN", "POWER_OUT", "NC"]
          },
          "signal_type": {
            "type": "string",
            "enum": ["DIGITAL", "ANALOG", "POWER", "RF", "NONE"]
          },
          "drive_type": {
            "type": "string",
            "enum": ["PUSH_PULL", "OPEN_DRAIN", "OPEN_SOURCE", "HIGH_Z", "CONFIGURABLE", "NONE"]
          },
          
          "electrical": {
            "type": "object",
            "description": "【核心】电气极限与阈值。最大亮点：支持数字或字符串公式表达式！",
            "properties": {
              "power_domain": { "type": "string", "description": "参考的电源逻辑引脚名，如 VDD/VIN" },
              "v_max": { "type": ["number", "string"], "description": "绝对最大耐压(V)，如 6.5 或 'VDD + 0.3'" },
              "v_min": { "type": ["number", "string"], "description": "绝对最小电压(V)，如 -0.3 或 'GND - 0.3'" },
              "i_max_ma": { "type": ["number", "string"], "description": "最大拉/灌电流(mA)" },
              "v_ih_min": { "type": ["number", "string"], "description": "输入高电平最小阈值，如 '0.7 * VDD'" },
              "v_il_max": { "type": ["number", "string"], "description": "输入低电平最大阈值，如 '0.3 * VDD'" },
              "v_oh_min": { "type": ["number", "string"] },
              "v_ol_max": { "type": ["number", "string"] }
            }
          },
          
          "rules": {
            "type": "object",
            "properties": {
              "pull_resistor": {
                "type": "string",
                "enum": ["REQUIRED_UP", "REQUIRED_DOWN", "INTERNAL_UP", "INTERNAL_DOWN", "CONFIGURABLE", "NONE"]
              },
              "unused_treatment": {
                "type": "string",
                "enum": ["FLOAT", "GND", "VCC", "PULL_UP", "PULL_DOWN", "FOLLOWER", "CUSTOM"]
              }
            }
          },
          
          "relations": {
            "type": "array",
            "description": "引脚间的特殊绑定关系",
            "items": {
              "type": "object",
              "properties": {
                "type": { "type": "string", "enum": ["DIFF_P", "DIFF_N", "COMPLEMENTARY"] },
                "target": { "type": "string", "description": "关联的逻辑引脚名" }
              }
            }
          }
        },
        "required": ["name", "packages", "direction", "signal_type"]
      }
    }
  }
}

```

---

### 二、 审核引擎如何利用该 Schema 回答你的 6 个问题？

1. **输入输出/电源信号？**：引擎直接读取 `direction` (判断流向) 和 `signal_type` (判断信号域)。
2. **电压/电流绝对最大值？**：读取 `electrical.v_max`。**如果遇到字符串（如 `"VDD + 0.3"`）**，审核引擎根据 `power_domain` 找到同芯片的 `VDD` 引脚，提取图纸中 VDD 连接的实际网络电压（如 3.3V），通过表达式引擎计算出真实绝对极限 `v_max = 3.6V`。
3. **两个 pin 是否能直连（兼容性）？**：
* *拓扑检查*：当 A 与 B 的 `drive_type` 都是 `PUSH_PULL` 且 `direction` 都是 `OUTPUT`，报短路错误。
* *电平检查*：A 的 `v_oh_min` 必须大于 B 的 `v_ih_min`。


4. **上下拉电阻？**：当发现某引脚 `drive_type` 为 `OPEN_DRAIN`，或 `rules.pull_resistor` 为 `REQUIRED_UP`，引擎会遍历该引脚所在的整个网络（Net），若没发现接往电源的上拉电阻，抛出 Error。
5. **未使用的 pin 如何处理？**：引擎找出原理图中悬空（No Connect）的引脚，检查 `rules.unused_treatment`。如果要求是 `GND` 却悬空，立刻报错。
6. **多封装变体？**：解析 EDA 网表时，引擎获知器件封装（如 `SOT-23-5`），使用该名称作为 Key 检索 `packages` 字典，即可得知图纸上的第 3 脚对应的逻辑功能是 `EN`，所有后续计算全部基于逻辑功能展开。

---

### 三、 4 个典型器件实战示例 (JSON 节点片段)

#### 1. LDO 线性稳压器 (例如：TPS7A20)

**核心痛点**：多封装映射、EN引脚禁止悬空、且耐压与输入引脚高度相关。

```json
{
  "name": "EN",
  "packages": {
    "SOT-23-5": [3],
    "X2SON-4": [4]
  },
  "direction": "INPUT",
  "signal_type": "DIGITAL",
  "drive_type": "NONE",
  "electrical": {
    "power_domain": "VIN",
    "v_max": "VIN",           // 引擎校验：EN引脚电压不能越级超过VIN电压
    "v_min": -0.3,
    "v_ih_min": 1.2
  },
  "rules": {
    "pull_resistor": "INTERNAL_DOWN",
    "unused_treatment": "VIN" // 若长开不用，强制要求接往输入电源，悬空报错
  }
}

```

#### 2. 数字开关 / I2C 器件 (例如：TCA9534 / 74LVC1G07)

**核心痛点**：开漏输出（Open-Drain），强制外部上拉，且通常支持 5V Tolerant（跨电平转换）。

```json
{
  "name": "SDA",
  "packages": { "SOIC-8": [1], "TSSOP-8": [1] },
  "direction": "BIDIRECTIONAL",
  "signal_type": "DIGITAL",
  "drive_type": "OPEN_DRAIN", 
  "electrical": {
    "power_domain": "VCC",
    "v_max": 5.5,               // 写死 5.5V，无视 VCC，引擎判定为支持 5V Tolerant
    "v_il_max": "0.3 * VCC",
    "v_ih_min": "0.7 * VCC",
    "v_ol_max": 0.4
  },
  "rules": {
    "pull_resistor": "REQUIRED_UP", // 引擎强校验点：必须找得到外部上拉
    "unused_treatment": "PULL_UP"
  }
}

```

#### 3. 运算放大器 (例如：LM358)

**核心痛点**：引脚间的差分对关系；闲置通道的严苛处理（需接跟随器，绝不能简单悬空或直接接地，否则容易引发自激震荡）。

```json
{
  "name": "IN1+",
  "packages": { "SOIC-8": [3], "VSSOP-8": [3] },
  "direction": "INPUT",
  "signal_type": "ANALOG",
  "drive_type": "NONE",
  "electrical": {
    "power_domain": "V+",
    "v_max": "V+ + 0.3",
    "v_min": "V- - 0.3"
  },
  "rules": {
    "pull_resistor": "NONE",
    "unused_treatment": "FOLLOWER" // 引擎识别此规则后，专项检查 IN- 是否连到 OUT，且 IN+ 是否给偏置
  },
  "relations": [
    {
      "type": "DIFF_P",
      "target": "IN1-"           // 引擎据此验证差分走线或阻抗匹配
    }
  ]
}

```

#### 4. MCU 微控制器 (例如：STM32G030)

**核心痛点**：IO 功能配置极度灵活，内部带可编程电阻。同一个芯片有多个 GND 引脚。

```json
{
  "name": "PA0",
  "packages": { 
    "LQFP48": [10], 
    "LQFP64": [14] 
  },
  "direction": "BIDIRECTIONAL",
  "signal_type": "DIGITAL",
  "drive_type": "CONFIGURABLE",
  "electrical": {
    "power_domain": "VDD",
    "v_max": "VDD + 3.6",       // 公式表达：当 VDD 为 3.3V 时，耐压逼近 7V (FT引脚)
    "v_ih_min": "0.7 * VDD",
    "v_il_max": "0.3 * VDD"
  },
  "rules": {
    "pull_resistor": "CONFIGURABLE", // 软件可配，外部硬件不强制要求
    "unused_treatment": "FLOAT"      // 硬件允许悬空，常规做法是软件配为模拟输入以省电
  }
},
{
  "name": "GND",
  "packages": {
    "LQFP48": [8, 23, 35, 47],  // 多个物理 GND 引脚合并映射到同一个逻辑 GND
    "QFN32": [4, 16, 28, "EP"]  // 包含底部散热焊盘
  },
  "direction": "POWER_IN",
  "signal_type": "POWER",
  "drive_type": "NONE",
  "rules": {
    "unused_treatment": "GND"
  }
}

```
