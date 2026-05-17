# Q1: 负压/负电流器件的 min/max 单调性验证

> Historical technical deep dive. This page preserves reasoning about one validation problem, but it is not the current repository architecture or coverage reference. For current facts, read [`current-state.md`](current-state.md), [`architecture.md`](architecture.md), and the relevant schema/export code first.

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

这是一个极其经典且硬核的电子工程/EDA数据处理问题。在解析各大原厂（如 TI、ADI 等）的 Datasheet 时，这种“逻辑陷阱”极其常见。

问题的根本原因在于：电子工程师在撰写 Datasheet 时，混用了**“代数表达（Algebraic）”**和**“幅值/绝对值表达（Magnitude）”**两种排版习惯。

要设计一个极具鲁棒性的通用规则引擎，绝对不能简单粗暴地套用 `abs()`（这会毁掉跨零点参数），而是需要构建一个**“双轨推断模型”**：**先推断单行数据遵循哪种约定，再将其统一映射到数轴上真实的物理代数区间 ，最后只对真实物理区间做包容性运算。**

---

### 💡 核心算法架构设计

不论 Datasheet 的字面怎么写，我们最终都将其转换为真实的数学上下限 `[L, U]`。算法分为三个关键步骤：

#### 1. 双轨单调性校验 (模式推断)

剔除空值后，提取到的一行数据 `(min, typ, max)` 只要满足以下**两种约定之一**即为合法：

* **代数约定（ALGEBRAIC）**：按数轴大小严格递增 `min ≤ typ ≤ max`。适用于正压、正电流、跨零双极性参数（如 Offset Voltage `-1mV ~ 1mV`）。
* **幅值约定（MAGNITUDE）**：按偏离 0 的绝对值大小递增排列，在数学上表现为**递减** `min ≥ typ ≥ max`，**且要求所有数值必须 ≤ 0**。适用于负压 LDO、负电流（如 LT1964 的 `-4.925 ≥ -5.0 ≥ -5.075`）。

#### 2. 映射绝对物理区间

* **在 ALGEBRAIC 下**：真实物理下限 `L = min`，物理上限 `U = max`。
* **在 MAGNITUDE 下**：物理含义发生**翻转**。字面的 `max` 代表最大幅值（即离 0 最远的负数），反而是代数真实极小值；`min` 代表最小幅值（离 0 最近）。因此反转映射：**`L = max`，`U = min**`。（若 min 缺失，负数的最小幅值默认为 `0.0`）。

#### 3. 跨温包容性校验

物理定律决定：全温（Full Temp）下的器件离散度更大，因此其物理容差区间必须**大于或等于**室温（25°C）区间。
这降维成了一个极其简单的数学子集判断：全温区间 `[L_FT, U_FT]` 必须包含 25°C 区间 `[L_25, U_25]`，即 **`L_FT ≤ L_25` 且 `U_FT ≥ U_25**`。

---

### 💻 通用验证算法实现 (Python)

以下是可以直接无缝集成到您规则引擎中的核心代码：

```python
import math

def get_supported_modes(min_val, typ_val, max_val):
    """
    推断单行数据支持的排版模式：ALGEBRAIC (代数) 或 MAGNITUDE (幅值)
    """
    vals = [v for v in [min_val, typ_val, max_val] if v is not None]
    
    # 无数据或单一边界时，两种模式在局部均有可能，留给跨温校验做决策
    if len(vals) <= 1:
        modes = ['ALGEBRAIC']
        # 只有负数或0，才有可能走幅值模式
        if not vals or vals[0] <= 0:
            modes.append('MAGNITUDE')
        return modes
        
    modes = []
    
    # 模式A：代数单调递增 (如 -0.1 <= 0 <= 0.5)
    if all(vals[i] <= vals[i+1] for i in range(len(vals)-1)):
        modes.append('ALGEBRAIC')
        
    # 模式B：幅值单调递增 (如 LT1964: -4.925 >= -5.0 >= -5.075)
    # 物理安全锁：必须所有数值 <= 0，才允许数值逆序
    if all(vals[i] >= vals[i+1] for i in range(len(vals)-1)) and all(v <= 0 for v in vals):
        modes.append('MAGNITUDE')
        
    return modes

def get_physical_interval(min_val, max_val, mode):
    """
    将字面的 min/max 映射为物理数轴上真实的代数区间 [Lower, Upper]
    """
    if mode == 'ALGEBRAIC':
        L = min_val if min_val is not None else -math.inf
        U = max_val if max_val is not None else math.inf
        return L, U
        
    elif mode == 'MAGNITUDE':
        # 幅值模式翻转：max 代表绝对值最大（最负的下界），min 代表绝对值最小（靠0的上界）
        L = max_val if max_val is not None else -math.inf
        U = min_val if min_val is not None else 0.0
        return L, U

def validate_row(min_val, typ_val, max_val):
    """单行数据质量自洽性校验"""
    modes = get_supported_modes(min_val, typ_val, max_val)
    if not modes:
        return False, "数据违反物理单调性 (可能是OCR提取错误或存在乱序正数)"
    return True, "Valid"

def validate_cross_temp(row_25, row_full):
    """
    跨温度包含性校验：全温的物理容差必然包裹 25°C 的物理容差
    输入格式示例: dict {'min': -4.925, 'typ': -5.0, 'max': -5.075}
    """
    modes_25 = get_supported_modes(row_25.get('min'), row_25.get('typ'), row_25.get('max'))
    modes_full = get_supported_modes(row_full.get('min'), row_full.get('typ'), row_full.get('max'))
    
    if not modes_25 or not modes_full:
        return False, "单行数据异常，无法进行跨温比对"
        
    # 寻找两种温度下均能解释得通的物理模式
    common_modes = set(modes_25) & set(modes_full)
    if not common_modes:
        return False, "全温与 25°C 数据的排版约定(代数 vs 幅值)存在冲突"
        
    eps = 1e-9 # 浮点精度容差
    for mode in common_modes:
        L_25, U_25 = get_physical_interval(row_25.get('min'), row_25.get('max'), mode)
        L_ft, U_ft = get_physical_interval(row_full.get('min'), row_full.get('max'), mode)
        
        # 核心物理规律：全温的代数区间必须 大于等于 25°C 区间
        if L_ft <= L_25 + eps and U_ft >= U_25 - eps:
            return True, f"验证通过 (底层映射基于 {mode} 约定)"
            
    return False, "验证失败：全温物理容差未能完全包裹 25°C 容差"

```

---

### 🚀 算法如何完美击破您的 4 个难题？

#### 1. 负压 LDO 输出 (LT1964 实例)

* **25°C 输入**：`min=-4.925, typ=-5, max=-5.075`
* **全温 输入**：`min=-4.85, max=-5.15`
* **算法轨迹**：
1. 发现 `-4.925 ≥ -5 ≥ -5.075` 且全为负数，触发安全锁锁定 `MAGNITUDE` 模式。
2. 区间翻转映射：25°C 区间变为 `L = -5.075`, `U = -4.925`。全温区间变为 `L = -5.150`, `U = -4.850`。
3. 子集比对：`[-5.15, -4.85]` 完全包容 `[-5.075, -4.925]`。完美通过！



#### 2. 只有单边限制的负电流参数

* **25°C 输入**：`typ=-3, max=-9`
* **全温 输入**：`max=-15` (没有 min 和 typ)
* **算法轨迹**：
1. 25°C 由于 `-3 ≥ -9` 锁定 `MAGNITUDE`。
2. 映射 25°C 区间：`L = max = -9`，因为无 min，默认取 `U = 0.0`。真实区间为 `[-9, 0]`。
3. 映射全温区间：同理补全为 `[-15, 0]`。
4. 比对：`[-15, 0]` 包容 `[-9, 0]`。完美通过。



#### 3. 混合参数 / 跨零点参数

* **输入**：`min=-0.1, typ=0.2, max=0.5`
* **算法轨迹**：严格按代数递增，识别为 `ALGEBRAIC`，物理区间直接映射为 `[-0.1, 0.5]`，无需任何翻转。
* **防呆拦截**：假设由于 PDF 解析错位导致 `min=5.1, typ=5.0, max=4.9`。虽然它递减，但**因为包含正数，不满足全负安全锁**，算法直接返回 `[]`，第一时间将脏数据精准拦截！

#### 4. 常温与全温的动态包容判定

由于上述算法剥离了字面“形式”，把所有数据还原为了**绝对真理的物理数轴上下限**。跨温度验证被降维打击为了极其简单的一句代码 `L_ft <= L_25 and U_ft >= U_25`。不论原厂 PDF 的表格写得多么特立独行，在统一数学模型面前均能被严密校验。
