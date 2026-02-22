# Q3: 原理图审核知识库的 Pin 定义 Schema 设计

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

*(请在此处粘贴超级 LLM 的回答)*
