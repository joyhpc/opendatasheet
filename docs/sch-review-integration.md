# OpenDatasheet → sch-review 对接文档

## 概述

OpenDatasheet 项目从 PDF datasheet 中提取结构化参数，输出为 `data/sch_review_export/` 目录下的 JSON 文件，供 sch-review 的 DRC 引擎消费。

**仓库**: https://github.com/joyhpc/opendatasheet
**导出目录**: `data/sch_review_export/`
**Schema**: `sch-review-device/1.0`
**当前覆盖**: 26 普通 IC + 4 FPGA 封装 = 30 个文件

---

## 文件命名规则

```
data/sch_review_export/
├── {MPN}.json              # 普通 IC，如 XL4003.json, RT9193.json
└── {Device}_{Package}.json # FPGA，如 XCKU3P_FFVB676.json
```

MPN 中的特殊字符 (`/`, ` `) 替换为 `_`。

---

## 数据结构

### 普通 IC (`_type: "normal_ic"`)

```json
{
  "_schema": "sch-review-device/1.0",
  "_type": "normal_ic",
  "mpn": "XL4003",
  "manufacturer": "XLSEMI",
  "category": "Buck",           // LDO / Buck / OpAmp / Switch / Logic / DAC / Interface / ...
  "description": "4A 300KHz 32V Buck DC to DC Converter",

  "packages": {
    "TO252-5L": {
      "pin_count": 6,
      "pins": {
        "1": {"name": "GND",  "direction": "POWER_IN", "signal_type": "POWER",   "description": "...", "unused_treatment": null},
        "2": {"name": "FB",   "direction": "INPUT",    "signal_type": "ANALOG",  "description": "...", "unused_treatment": null},
        "3": {"name": "SW",   "direction": "OUTPUT",   "signal_type": "POWER",   "description": "...", "unused_treatment": null},
        "4": {"name": "EN",   "direction": "INPUT",    "signal_type": "DIGITAL", "description": "...", "unused_treatment": "PULL_UP"},
        "5": {"name": "VIN",  "direction": "POWER_IN", "signal_type": "POWER",   "description": "...", "unused_treatment": null},
        "TAB": {"name": "SW", "direction": "OUTPUT",   "signal_type": "POWER",   "description": "...", "unused_treatment": null}
      }
    }
  },

  "absolute_maximum_ratings": {
    "VIN": {"parameter": "Supply Input Voltage", "min": null, "max": 35.0, "unit": "V", "conditions": null}
  },

  "electrical_parameters": {
    "VFB": {"parameter": "Feedback Voltage", "min": 0.762, "typ": 0.8, "max": 0.838, "unit": "V", "conditions": null}
  },

  "drc_hints": {
    "vin_abs_max":    {"value": 35.0, "unit": "V"},
    "vref":           {"min": 0.762, "typ": 0.8, "max": 0.838, "unit": "V"},
    "iout_operating": {"typ": null, "max": 4.0, "unit": "A"},
    "iq":             {"typ": 5.0, "max": 7.0, "unit": "mA"},
    "enable_threshold": {"min": 1.4, "typ": 1.5, "max": null, "unit": "V"}
  }
}
```

**字段说明**:

| 字段 | 用途 |
|------|------|
| `packages[pkg].pins[pin_num]` | 通过物理 pin number 查 pin 功能。key 与 `DeviceInfo.pins` 的 key 一致 |
| `pins[].direction` | 信号方向: `INPUT` / `OUTPUT` / `BIDIRECTIONAL` / `POWER_IN` / `POWER_OUT` / `PASSIVE` / `OPEN_DRAIN` |
| `pins[].signal_type` | 信号类型: `POWER` / `DIGITAL` / `ANALOG` |
| `pins[].unused_treatment` | 未使用时处理: `PULL_UP` / `PULL_DOWN` / `null`(必须连接) |
| `drc_hints.vref` | **FB 分压器反算 Vout 的关键参数**。Stage 7 用 `Vout = Vref * (1 + R_upper/R_lower)` |
| `drc_hints.vin_abs_max` | 输入电压绝对最大值，用于过压检查 |
| `absolute_maximum_ratings` | 完整的绝对最大额定值表 |
| `electrical_parameters` | 完整的电气参数表 |

### FPGA (`_type: "fpga"`)

```json
{
  "_schema": "sch-review-device/1.0",
  "_type": "fpga",
  "mpn": "XCKU3P",
  "package": "FFVB676",

  "supply_specs": {
    "VCCINT_Standard": {"symbol": "VCCINT", "min": 0.825, "typ": 0.85, "max": 0.876, "unit": "V", "conditions": "Standard"}
  },

  "io_standard_specs": {
    "VCCO_LVDS_25": {"symbol": "VCCO", "min": 2.375, "typ": 2.5, "max": 2.625, "unit": "V", "io_standard": "LVDS_25"}
  },

  "power_rails": {
    "VCCINT":   {"voltage": 0.85, "tolerance": "±3%", "desc": "Internal core supply"},
    "MGTAVCC":  {"voltage": 0.9,  "tolerance": "±3%", "desc": "GT analog core supply"},
    "MGTAVTT":  {"voltage": 1.2,  "tolerance": "±5%", "desc": "GT TX/RX termination supply"}
  },

  "banks": {
    "64": {
      "io_type": "HP",
      "io_pins": 52,
      "supported_vcco": [1.0, 1.2, 1.35, 1.5, 1.8],
      "vref_capable_pins": ["AC17", "AB17"],
      "clock_capable_pins": ["AD18", "AC18", ...],
      "drc_note": "HP bank: all IOs in same bank must use compatible IO standards sharing same VCCO"
    }
  },

  "diff_pairs": [
    {"type": "IO",       "pair_name": "IO_L10_64", "p_pin": "AA22", "n_pin": "AB22", "bank": "64", "io_type": "HP"},
    {"type": "GT_RX",    "pair_name": "RX_0_224",  "p_pin": "AF2",  "n_pin": "AF1",  "bank": "224"},
    {"type": "GT_REFCLK","pair_name": "REFCLK0_224","p_pin": "AB7", "n_pin": "AB6",  "bank": "224"}
  ],

  "drc_rules": {
    "power_integrity":        {"severity": "ERROR",   "desc": "All power and ground pins must be connected"},
    "config_pins":            {"severity": "ERROR",   "desc": "Mandatory config pins must be connected"},
    "vcco_bank_consistency":  {"severity": "ERROR",   "desc": "All IO in same bank must use compatible IO standards"},
    "diff_pair_integrity":    {"severity": "ERROR",   "desc": "Differential pairs must be used together or not at all"},
    "gt_power":               {"severity": "ERROR",   "desc": "GT power rails must be connected even if GT not used"},
    "config_mode_consistency":{"severity": "ERROR",   "desc": "M[2:0] pin levels must match intended configuration mode"},
    "rsvdgnd":                {"severity": "ERROR",   "desc": "RSVDGND pins must connect to GND"},
    "unused_io":              {"severity": "WARNING", "desc": "Unused IO pins should not be left floating"}
  },

  "pins": [
    {"pin": "AF1", "name": "MGTYRXN0_224", "bank": "224", "io_type": "GTY", "function": "GT_RX", "polarity": "N", "gt_type": "GTY", "lane": 0, "gt_bank": 224},
    {"pin": "Y11", "name": "CCLK_0",       "bank": "0",   "io_type": "CONFIG", "function": "CONFIG", "drc": {"must_connect": true, "pull": null, "desc": "Config clock."}},
    {"pin": "W11", "name": "RSVDGND",      "bank": null,  "function": "GROUND", "drc": {"must_connect": true, "net": "GND", "critical": true}}
  ],

  "lookup": {
    "pin_to_name": {"AF1": "MGTYRXN0_224", "Y11": "CCLK_0", ...},
    "name_to_pin": {"MGTYRXN0_224": "AF1", "CCLK_0": "Y11", ...},
    "io_pins":     ["AA18", "Y18", ...],
    "power_pins":  ["AA11", "AD12", ...],
    "config_pins": ["Y11", "AD11", ...],
    "gt_pins":     ["AB6", "AB7", ...]
  }
}
```

---

## sch-review 调用方式

### 1. 加载器件知识库

```python
import json
from pathlib import Path

EXPORT_DIR = Path("opendatasheet/data/sch_review_export")

def load_device_kb(mpn: str, package: str = None) -> dict | None:
    """根据 MPN 加载器件知识库。FPGA 需要指定 package。"""
    if package:
        path = EXPORT_DIR / f"{mpn}_{package}.json"
    else:
        # 尝试精确匹配，再尝试模糊匹配
        path = EXPORT_DIR / f"{mpn}.json"
        if not path.exists():
            # 处理 MPN 中的特殊字符
            safe = mpn.replace("/", "_").replace(" ", "_")
            path = EXPORT_DIR / f"{safe}.json"
    
    if path.exists():
        return json.loads(path.read_text())
    return None
```

### 2. 普通 IC — Pin 功能查询

```python
# 场景: Stage 7 需要知道 U5 pin 4 是什么功能
device_kb = load_device_kb("JW5359M")  # 从 BOM value 匹配

# 方法 1: 已知封装名
pin_info = device_kb["packages"]["SOT-23-6"]["pins"]["4"]
# → {"name": "VFB", "direction": "INPUT", "signal_type": "ANALOG", ...}

# 方法 2: 遍历所有封装找 pin (封装名不确定时)
for pkg_name, pkg in device_kb["packages"].items():
    if "4" in pkg["pins"]:
        pin_info = pkg["pins"]["4"]
        break
```

### 3. 普通 IC — FB 分压器反算 Vout

```python
# 场景: Stage 7 v3 从 FB 分压器反算 Vout，需要 Vref
device_kb = load_device_kb("XL4003")
vref = device_kb["drc_hints"].get("vref", {}).get("typ")
# → 0.8 (V)

# 已知 R_upper 和 R_lower (从网表中 FB pin 连接的分压电阻获取)
if vref and r_upper and r_lower:
    vout = vref * (1 + r_upper / r_lower)
```

### 4. 普通 IC — 电压越限检查

```python
# 场景: 检查 U5 的 VIN 是否超过绝对最大额定值
device_kb = load_device_kb("XL4003")
vin_max = device_kb["drc_hints"].get("vin_abs_max", {}).get("value")
# → 35.0 (V)

# 从网表推导出 VIN net 的实际电压
if actual_vin > vin_max:
    report_error(f"U5 VIN={actual_vin}V exceeds abs max {vin_max}V")
```

### 5. FPGA — Pin 功能查询

```python
# 场景: 检查 FPGA U1 的 pin AF1 连接是否正确
fpga_kb = load_device_kb("XCKU3P", package="FFVB676")

# 通过 pin number 查 pin name
pin_name = fpga_kb["lookup"]["pin_to_name"]["AF1"]
# → "MGTYRXN0_224"

# 获取完整 pin 信息
pin_info = next(p for p in fpga_kb["pins"] if p["pin"] == "AF1")
# → {"function": "GT_RX", "bank": "224", "polarity": "N", "gt_type": "GTY", "lane": 0, ...}
```

### 6. FPGA — Bank VCCO 兼容性检查

```python
# 场景: 检查连接到 Bank 64 的 IO 标准是否与 VCCO 电压兼容
bank = fpga_kb["banks"]["64"]
# → {"io_type": "HP", "supported_vcco": [1.0, 1.2, 1.35, 1.5, 1.8]}

# 从网表获取 VCCO_64 net 的实际电压
if actual_vcco not in bank["supported_vcco"]:
    report_error(f"Bank 64 VCCO={actual_vcco}V not in supported list")
```

### 7. FPGA — CONFIG Pin 必连检查

```python
# 场景: 检查所有 CONFIG pin 是否正确连接
config_pins = [p for p in fpga_kb["pins"] if p["function"] == "CONFIG"]
for pin in config_pins:
    drc = pin.get("drc", {})
    if drc.get("must_connect") == True:
        if pin["pin"] not in connected_pins:
            report_error(f"CONFIG pin {pin['pin']} ({pin['name']}) must be connected. {drc.get('desc','')}")
        if drc.get("pull"):
            # 检查是否有正确的上拉/下拉
            report_info(f"{pin['name']} requires {drc['pull']}")
```

### 8. FPGA — 差分对完整性检查

```python
# 场景: 如果差分对的一个 pin 被使用，另一个也必须使用
for pair in fpga_kb["diff_pairs"]:
    p_used = pair["p_pin"] in connected_pins
    n_used = pair["n_pin"] in connected_pins
    if p_used != n_used:
        report_error(f"Diff pair {pair['pair_name']}: only one pin connected (P={pair['p_pin']} N={pair['n_pin']})")
```

### 9. FPGA — 电源完整性检查

```python
# 场景: 检查所有电源/地 pin 是否连接
for pin in fpga_kb["pins"]:
    if pin["function"] in ("POWER", "GROUND", "GT_POWER"):
        if pin["pin"] not in connected_pins:
            severity = "CRITICAL" if pin.get("drc", {}).get("critical") else "ERROR"
            report(severity, f"Power pin {pin['pin']} ({pin['name']}) not connected")
```

---

## MPN 匹配策略

sch-review 的 `DeviceInfo.value` (如 `JW5359M`) 需要匹配到 export 文件。建议:

1. 精确匹配: `value` == export 文件的 `mpn`
2. 前缀匹配: `value` startswith export `mpn` (处理后缀变体如 `RT9193-33PB`)
3. BOM 映射表: 维护一个 `{bom_value: export_mpn}` 的手动映射 (处理完全不同的命名)

FPGA 还需要从 `DeviceInfo.primitive` 中提取封装信息来匹配正确的 pinout 文件。

---

## 数据更新流程

```bash
cd opendatasheet

# 1. 新增 PDF → 提取参数 (已有 pipeline)
python3 scripts/run_pipeline.py data/raw/new_device.pdf

# 2. FPGA pinout → 解析 (如果是新 FPGA)
python3 scripts/parse_fpga_pinout.py

# 3. 导出给 sch-review
python3 scripts/export_for_sch_review.py

# 输出在 data/sch_review_export/
```
