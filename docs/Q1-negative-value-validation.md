# Q1: 负压/负电流器件的 min/max 单调性验证

## 问题

我在开发一个电子元器件 datasheet 自动提取和验证系统。系统从 PDF datasheet 中提取电气参数的 min/typ/max 值，然后用规则引擎验证数据质量。

当前的单调性规则是：min ≤ typ ≤ max

但遇到负压 LDO（如 LT1964，输出 -5V）时，datasheet 原文写的是：
```
Regulated Output Voltage: min=-4.925V, typ=-5V, max=-5.075V
```

这里 min > typ > max（数值上），但从物理含义上看是正确的：
- -4.925V 是"最小偏离"（绝对值最小），-5.075V 是"最大偏离"（绝对值最大）

类似的还有负电流参数：
```
SHDN Pin Current (VSHDN=-15V): typ=-3µA, max=-9µA
```

请设计一个通用的验证规则，能同时正确处理：
1. 正压/正电流参数（常规 min ≤ typ ≤ max）
2. 负压/负电流参数（min/max 含义反转）
3. 混合参数（如 Shutdown Threshold 同时有正负值行）
4. 跨温度范围验证（25°C 范围应被 full temp 范围包含）

要求：
- 给出明确的判断算法（伪代码或 Python）
- 不能简单地取绝对值（因为有些参数确实是有符号的）
- 需要考虑 datasheet 中 min/max 的真实物理含义

---

## 答案

*(请在此处粘贴超级 LLM 的回答)*
