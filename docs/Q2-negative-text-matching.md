# Q2: PDF 交叉验证中负数值的文本匹配

> Historical technical deep dive. This page preserves reasoning about one validation problem, but it is not the current repository architecture or coverage reference. For current facts, read [`current-state.md`](current-state.md), [`architecture.md`](architecture.md), and the relevant schema/export code first.

## 问题

我在开发一个 datasheet 提取验证系统。其中一个验证步骤是"交叉验证"：将 AI 提取的数值与 PDF 原始文本进行匹配，确认提取值确实存在于原文中。

当前方法：用 PyMuPDF 提取页面文本，然后搜索数值字符串。

问题：对于负压器件（如 LT1964），PDF 原文中的负号表示方式多样：
1. 标准减号 "-" (U+002D)
2. En dash "–" (U+2013)
3. Em dash "—" (U+2014)
4. Minus sign "−" (U+2212)
5. 有时负号和数字之间有空格："– 5.075"
6. 有时用 ±：如 "±20V" 表示 -20V 到 +20V
7. 有时用逗号分隔范围："–0.5V, 20V" 表示 min=-0.5, max=20

实际案例：
```
PDF 原文: "–4.925  –5  –5.075" (使用 en dash)
提取值: [-4.925, -5.0, -5.075] (使用标准减号)
直接字符串搜索 "-4.925" 找不到 "–4.925"
```

请设计一个健壮的数值匹配算法：
1. 能处理所有负号变体
2. 能处理 ± 表示
3. 能处理范围表示（逗号分隔）
4. 能处理数值格式差异（如 5 vs 5.0 vs 5.00）
5. 给出 Python 实现

---

## 答案

在处理 Datasheet 这类排版极其复杂、充斥着历史遗留编码（如 PDF 导出造成的字符映射）的工业文档时，**继续依靠“字符串直接搜索”或“正则提取子串”是注定会遇到组合爆炸的（如 `5` vs `5.0`，全角/半角/En-dash 变体，空格不均等）**。

解决这个痛点的高维/降维打击方案是：**“全量正向解析 + 语义级浮点数学比对（Semantic Numeric Matching）”**。

### 核心解题思路

1. **构建“数值备选池”**：不要试图将 AI 提取的值转回正则去文本中找；相反，我们要用包容性极强的正则表达式，将 PDF 文本段落里的**所有潜在数值片段全部抓取出来，并统一转化为 Python `float`。**
2. **符号与范围智能消歧（核心启发式算法）**：
在 `0 - 5.0V` 中，`-` 是范围分隔符（提取正数 5.0）；在 `Pin 1 -5.0V` 或 `– 5.075` 中，它是负号（提取负数 -5.0）。
我们可以通过**空格的对称性（Space Symmetry）以及前置字符语法**，来精准判断该符号的作用，消除极性歧义。
3. **数学比对容差**：拿着 AI 提取的 float 目标值，去池子中使用 `math.isclose()` 校验。这样 `5` 和 `5.00`，`1.5e-3` 和 `0.0015` 将自然通过验证。

---

### 健壮的 Python 实现

这段代码没有第三方库依赖，非常轻量，且直接解决了你提到的 6 大边缘痛点：

```python
import re
import math
from typing import Union, List

class DatasheetValueValidator:
    def __init__(self, rel_tol: float = 1e-5, abs_tol: float = 1e-8):
        """
        :param rel_tol: 相对误差容差 (例如 1e-5 意味着允许 0.001% 的浮点精度差异)
        :param abs_tol: 绝对误差容差，主要用于处理等于或极度接近 0 的对比
        """
        self.rel_tol = rel_tol
        self.abs_tol = abs_tol
        
        # 1. 涵盖所有由于 PDF 导出而产生的减号变体: 
        # 标准减号, Non-breaking hyphen, Figure dash, En dash(–), Em dash(—), 数学减号(−)
        self.minus_chars = '-\u2010\u2011\u2012\u2013\u2014\u2212'
        
        # 2. 基础数值正则：支持千分位格式 (10,000.5)、普通小数 (5.0)、无前导零小数 (.5)
        self.base_num_pattern = r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+'
        
        # 3. 科学计数法后缀：如 e-3, E+05 (内部连字符同样支持变体)
        mc_escaped = self.minus_chars.replace('-', r'\-')
        self.exp_pattern = fr'(?:[eE]\s*[+{mc_escaped}]?\s*\d+)?'
        
        # 最终组合抓取正则
        self.regex = re.compile(fr'({self.base_num_pattern}{self.exp_pattern})')

    def extract_floats_from_text(self, raw_text: str) -> List[float]:
        """
        将 PDF 原始文本中的所有数值完全转化为浮点数，并智能推断极性。
        """
        parsed_numbers = []
        mc_escaped = self.minus_chars.replace('-', r'\-')
        
        for match in self.regex.finditer(raw_text):
            num_str = match.group(1)
            
            # 清理字符串以便 Python float() 可以安全转换
            clean_num = num_str.replace(',', '').replace(' ', '')
            for mc in self.minus_chars:
                clean_num = clean_num.replace(mc, '-')
                
            try:
                val = float(clean_num)
            except ValueError:
                continue
                
            # --- 极性与上下文智能分析 ---
            start_idx = match.start()
            preceding = raw_text[:start_idx]
            preceding_stripped = preceding.rstrip()
            
            signs = [1.0] # 默认为正数
            
            if preceding_stripped:
                last_char = preceding_stripped[-1]
                
                # 场景 A: 明确的 ± 号 (产生正负两个可能)
                if last_char == '±':
                    signs = [1.0, -1.0]
                    
                # 场景 B: 包含各类减号的变体
                elif last_char in self.minus_chars:
                    # 判断是否是文本型加减号，如 "+/-" 或 "+ / -"
                    if re.search(fr'\+/?\s*[{mc_escaped}]$', preceding_stripped):
                        signs = [1.0, -1.0]
                    else:
                        # 核心难点：纯减号消歧 (它是 Range连字符 还是 负号？)
                        before_minus_exact = preceding_stripped[:-1]
                        before_minus_stripped = before_minus_exact.rstrip()
                        
                        # 分析减号前后的空格不对称性
                        whitespace_before = before_minus_exact[len(before_minus_stripped):]
                        whitespace_after = preceding[len(preceding_stripped):]
                        
                        space_before = len(whitespace_before)
                        space_after = len(whitespace_after)
                        
                        # 分析前一个词是否包含数字 (用于区分 "VOUT = -5" 和 "0 - 5")
                        has_digit = False
                        words = before_minus_stripped.split()
                        if words:
                            last_word = words[-1]
                            if any(c.isdigit() for c in last_word):
                                has_digit = True
                            elif len(words) >= 2 and any(c.isdigit() for c in words[-2]):
                                # 容忍常见的附加单位如 V, mA
                                if last_word.isalpha() and len(last_word) <= 3 and last_word.lower() not in ["to", "and", "or"]:
                                    has_digit = True
                                    
                            # 如果前缀属于强制赋值或罗列（例如 "V2:", "VOUT =", "-0.5,"），上下文重置，必为负数
                            if last_word.endswith(':') or last_word.endswith('=') or last_word.endswith(','):
                                has_digit = False
                                    
                        # 综合推断
                        if has_digit:
                            if space_before >= 2 or '\n' in whitespace_before or '\t' in whitespace_before:
                                is_range = False # 空格极大，属排版列 (如 "0       -5") -> 负号
                            elif space_before == space_after:
                                is_range = True  # 对称 (如 "0-5", "0 - 5") -> 范围
                            elif space_before > space_after:
                                is_range = False # 不对称粘连 (如 "Pin 1 -5V") -> 负号
                            else:
                                is_range = True  # 前无后有 (如 "0- 5V") -> 范围
                        else:
                            is_range = False     # 前面根本没有前置数字 -> 肯定属于负号
                            
                        if not is_range:
                            signs = [-1.0]
                            
                # 场景 C: 明确的正号
                elif last_char == '+':
                    signs = [1.0]
                    
            # 将推演的所有可能数值压入池中
            for s in signs:
                final_val = val * s
                if final_val == -0.0: final_val = 0.0
                parsed_numbers.append(final_val)
                
        return parsed_numbers

    def is_value_in_text(self, target_value: Union[float, int, str], raw_text: str) -> bool:
        """
        验证 AI 提取的数值目标，是否真实验证存在于这句原文的逻辑中。
        """
        try:
            if isinstance(target_value, str):
                target_value = target_value.replace(',', '')
            target_float = float(target_value)
        except (ValueError, TypeError):
            return False
            
        extracted_numbers = self.extract_floats_from_text(raw_text)
        
        # 语义级比对：无视 5 vs 5.0，无视 -0.0
        for num in extracted_numbers:
            if math.isclose(target_float, num, rel_tol=self.rel_tol, abs_tol=self.abs_tol):
                return True
                
        return False

```

### 痛点验证与原理解析

将你的业务场景直接输入，我们看看它是如何化解的：

```python
validator = DatasheetValueValidator()

test_cases = [
    # 痛点 1 & 2: 各种特殊减号 (En dash) 与带空格的悬空负号
    ("–4.925  –5  – 5.075", [-4.925, -5.0, -5.075], True), 
    
    # 痛点 3: 处理 ± 范围衍生出正负两值
    ("Max Absolute: ±20V", [20.0, -20.0], True),
    ("Also supports +/- 10", [10, -10], True),
    
    # 痛点 4: 逗号分隔的跨负正极范围列表
    ("Range: –0.5V, 20V", [-0.5, 20.0], True),
    ("Values: -0.5, -5.0", [-0.5, -5.0], True), # 不会因为逗号错误切分
    
    # 痛点 5: 数值格式（千分位、科学计数与小数差异）
    ("Current: 10,000", [10000.0], True),
    ("Limit: 5", [5.00], True),
    
    # 痛点 6: 极致智能排雷 - 它懂什么是“范围分隔符”，什么是“负号”
    ("0-5.0V", [5.0], True),      # 对称连字符，是正数范围
    ("0-5.0V", [-5.0], False),    # 阻断把范围错误理解为负数
    ("Pin 1 -5.0V", [-5.0], True),# 不对称粘连，识别为打字错误的独立负号
    ("V2: - 5.0V", [-5.0], True)  # 冒号强行重置上下文，必定是负号
]

for text, targets, expected in test_cases:
    print(f"\n文本段落: '{text}'")
    for t in targets:
        result = validator.is_value_in_text(t, text)
        status = "✅通过" if result == expected else "❌异常"
        print(f"[{status}] 验证: {str(t):>8} 存在 -> 结果: {result}")

```

### 为什么该方案极其健壮且好用？

1. **彻底免疫编码泥潭**：通过 `self.minus_chars` 的收容池，不管是 InDesign 导出的 **En-dash (`–`)** 还是 MathType 生成的 **Minus sign (`−`)**，在解析之前都会被底层透明映射掉，从此不必再为正则漏抓符号头疼。
2. **天然分割逗号干扰**：正则核心使用 `\d{1,3}(?:,\d{3})+|\d+`。当你输入 `–0.5, 20` 时，正则发现逗号后是空格（不满足连续三个数字的千分位），它会自动在此断开。结果就是**天然完美抽出 `-0.5` 和 `20.0` 两个独立的项**。
3. **Space Symmetry（空间对称分析）**：这是消灭误伤的核心。如果是 `0 - 5.0` (1 空格:1 空格)，代表区间，取正数；但由于很多旧版 PDF 有 Typo，如 `Pin 1 -5.0V`，此时符号左侧有 1 个空格，右侧 0 个空格，算法判定这种“非对称粘连”为负号；甚至像 `–4.925  –5`，因为空格极其宽（2 空格），它也能准确识别这是排版列表中的负号，而不是一个错误的连字符。
