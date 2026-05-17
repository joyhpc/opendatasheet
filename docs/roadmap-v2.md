# OpenDatasheet 下一步计划

> Historical planning note. The counts and priorities below are not current
> repository facts. For the audited current state, read `docs/current-state.md`.
> For implemented architecture, read `docs/architecture.md`.

> Sirius 🌟 | 2026-02-25 | 基于 Axiom (sch-review) Issue #2 的需求分析

---

## 现状总结

| 指标 | 数值 |
|------|------|
| PDF 总量 | 346 |
| 已提取 (extracted_v2) | 143 (批处理进行中，目标 309+) |
| 已导出 (sch_review_export) | 85 (53 IC + 31 FPGA) |
| 待导出 | 90 个已提取但未导出 |
| IC 类别 | LDO 41, Buck 38, Switch 14, Logic 4, Interface 3, Other 42 |

### drc_hints 覆盖率（当前 53 个 IC export）

| 字段 | 覆盖率 | 原因 |
|------|--------|------|
| vin_abs_max | 40% | key 匹配太窄，只匹配 VIN/Vin/VI |
| vin_operating | 15% | 同上 |
| vref | 9% | 只匹配 VFB/VREF，漏掉 V_REF/Vfb 等变体 |
| vout | 8% | 只匹配 VOUT/Vout/VO |
| enable_threshold | 6% | 只匹配 VEN/VIH_EN，漏掉 VTH_EN 等 |
| iout | 25% | 只匹配 IOUT/IO/ILIM |
| iq | 17% | 只匹配 IQ/Iq |

**根本问题**：Gemini Vision 提取的 symbol key 命名不统一（VIN vs V(IN) vs Vin vs V_IN），硬编码匹配覆盖率极低。

---

## Phase 1: 立即可做（不改管线，1-2 小时）

### 1.1 重写 drc_hints 提取逻辑

从硬编码 key 匹配改为**语义模糊匹配**：

```python
# 当前：只匹配 ["VIN", "Vin", "VI"]
# 改为：正则 + parameter 文本搜索
def _find_param(elec_params, patterns, param_patterns=None):
    """模糊匹配 symbol key 或 parameter 描述"""
    for key, val in elec_params.items():
        for pat in patterns:
            if re.match(pat, key, re.IGNORECASE):
                return key, val
    if param_patterns:
        for key, val in elec_params.items():
            param_text = val.get('parameter', '')
            for pat in param_patterns:
                if re.search(pat, param_text, re.IGNORECASE):
                    return key, val
    return None, None
```

新增提取字段：
- `fsw_default` — 从 fSW/FOSC/fsw 等 symbol 或 "switching frequency" 描述匹配
- `soft_start_time` — 从 tSS/ISS 或 "soft start" 描述匹配
- `thermal_shutdown` — 从 TSD/TJSD 或 "thermal shutdown" 描述匹配
- `thermal_resistance` — 从 θJA/RθJA 或 "junction-to-ambient" 描述匹配
- `dropout_voltage` — 从 VDO/VDROP 或 "dropout" 描述匹配
- `output_voltage_fixed` — 固定输出 LDO 的 VOUT
- `reset_threshold` — 复位 IC 的监控阈值
- `output_type` — push-pull/open-drain（从 pin description 推断）

### 1.2 批量重新导出

跑 `export_for_sch_review.py` 把 143 个已提取的全部导出（当前只导出了 53 个）。

### 1.3 L2 单位白名单扩展

把 128 个 "Suspicious unit" 误报修掉，加入 `nV/√Hz`、`ppm/°C`、`%VOUT` 等 20 种常见复合单位。

---

## Phase 2: 管线增强（需改 pipeline_v2.py，2-4 小时）

### 2.1 L0 页面分类扩展

新增 `application` 类别，识别 Application Information / Typical Application / Design Guide 页面：

```python
APPLICATION_PATTERNS = [
    r'(?i)application\s+(information|circuit|note|example)',
    r'(?i)typical\s+application',
    r'(?i)design\s+guide',
    r'(?i)component\s+selection',
    r'(?i)inductor\s+selection',
    r'(?i)capacitor\s+selection',
    r'(?i)layout\s+(guide|recommendation)',
]
```

### 2.2 L1c: Application Info 提取

新的 Vision 提取阶段，专门从 Application 页面提取：

```json
{
  "recommended_components": {
    "input_capacitor": {"min": 10, "typ": 22, "unit": "uF", "type": "ceramic X5R/X7R", "voltage_rating": ">=25V"},
    "output_capacitor": {"min": 22, "typ": 47, "unit": "uF", "type": "ceramic X5R/X7R"},
    "inductor": {"min": 4.7, "max": 22, "unit": "uH", "isat_min": "1.3x Iout", "dcr_max": "50mΩ"},
    "boot_capacitor": {"typ": 0.1, "unit": "uF"},
    "compensation_network": {"type": "Type II", "components": {...}}
  },
  "design_equations": {
    "vout": "Vout = Vref × (1 + R1/R2)",
    "fsw_vs_rt": "fsw = 48000 / RT(kΩ)",
    "inductor_selection": "L = Vout × (Vin - Vout) / (Vin × fsw × ΔIL)"
  }
}
```

### 2.3 Schema v1.1 更新

在 `sch-review-device.schema.json` 中新增：
- `recommended_components` 对象
- `design_equations` 对象
- `drc_hints` 扩展字段定义

---

## Phase 3: 覆盖率提升（持续）

### 3.1 缺失 PDF 获取

需要父亲提供或从网上下载的器件：
- TLV70725 (TI LDO)
- JW7221 (保护 IC)
- XCAU15P (Xilinx FPGA)
- STM32H745 (ST MCU)
- DS90LV019 (TI LVDS)

### 3.2 批处理完成后全量重新导出

309 个 PDF 全部提取完成后，用升级后的 export 脚本重新导出全部。

### 3.3 FPGA 覆盖扩展

XCAU15P 需要：
- 从 AMD 下载 pinout 文件
- 解析 DC 特性
- 导出 sch-review 格式

---

## Phase 4: 远期（Axiom 第三层需求）

| 需求 | 方案 | 复杂度 |
|------|------|--------|
| 电源时序约束 | 从 datasheet "Power Sequencing" 章节提取 | 中 |
| I2C/SPI 地址映射 | 从 pin description + register map 推断 | 中 |
| 热设计参数 | θJA/θJC 已在电气参数中，需归类到 drc_hints | 低 |
| 兼容替代料 | 需要建立 pin-compatible 数据库 | 高 |
| 寄存器 map | 页面已识别，需新的提取 prompt | 高 |

---

## 执行优先级

```
Phase 1.1 (drc_hints 重写)     ← 立即开始，影响最大
Phase 1.2 (批量重新导出)        ← Phase 1.1 完成后立即跑
Phase 1.3 (L2 白名单)          ← 顺手修
Phase 2.1 (Application 分类)   ← 下一步
Phase 2.2 (L1c 提取)           ← 核心增强
Phase 3   (覆盖率)             ← 持续进行
Phase 4   (远期)               ← 按需
```

**预计 Phase 1 完成后，drc_hints 覆盖率从 6-40% 提升到 70-90%。**
**Phase 2 完成后，Axiom 第一层+第二层需求基本满足。**
