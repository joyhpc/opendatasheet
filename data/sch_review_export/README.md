# sch_review_export — 器件数据库

供原理图审核/解析工具使用的结构化器件数据。

## 使用方法

```python
import json

# 加载 manifest 获取所有器件列表
manifest = json.load(open("_manifest.json"))

# 按 MPN 查找器件
device = json.load(open("GW5AT-60_UG225.json"))

# 查 pin
pin_info = device["lookup"]["by_pin"]["A1"]   # pin号 → 名称
pin_num  = device["lookup"]["by_name"]["VCC"]  # 名称 → pin号

# 查电源规格
for name, spec in device["supply_specs"].items():
    print(f"{name}: {spec['min']}~{spec['max']}V")
```

## 文件结构

```
_manifest.json          # 索引，列出所有器件及摘要
GW5AT-15_MG132.json     # FPGA: {device}_{package}.json
GW5AT-60_UG225.json
XCKU3P_FFVA676.json
RT9193.json             # 普通IC: {MPN}.json
AMS1117.json
```

## FPGA Schema (`_type: "fpga"`)

| 字段 | 说明 |
|------|------|
| `mpn` | 器件型号 (GW5AT-60) |
| `manufacturer` | 厂商 (Gowin / AMD) |
| `package` | 封装 (UG225) |
| `supply_specs` | 推荐工作电压 (min/max/unit/conditions) |
| `absolute_maximum_ratings` | 绝对最大值 |
| `io_standard_specs` | IO 电平标准 (LVCMOS/LVDS/SSTL...) |
| `power_rails` | 电源域及其管脚 |
| `banks` | Bank 结构 (IO 数量, 管脚列表) |
| `diff_pairs` | 差分对 (true_pin/comp_pin/bank) |
| `drc_rules` | DRC 规则模板 |
| `pins[]` | 完整管脚列表 |
| `lookup.by_pin` | pin号 → 名称 |
| `lookup.by_name` | 名称 → pin号 |

## 普通 IC Schema (`_type: "normal_ic"`)

| 字段 | 说明 |
|------|------|
| `mpn` | 器件型号 |
| `manufacturer` | 厂商 |
| `category` | 分类 (LDO/Buck/OpAmp/Switch/Logic...) |
| `packages{}` | 封装 → {pin_count, pins[]} |
| `absolute_maximum_ratings{}` | 绝对最大值 |
| `electrical_parameters{}` | 电气参数 (min/typ/max) |
| `drc_hints[]` | DRC 检查提示 |

## 器件覆盖

### Gowin FPGA (9 files)
- GW5AT-15: MG132, CS130, CS130F
- GW5AT-60: UG225, PG484A, UG324S
- GW5AT-138: FPG676A
- GW5AR-25: UG256P
- GW5AS-25: UG256

### AMD FPGA (4 files)
- XCKU3P: FFVA676, FFVB676, FFVD900, SFVB784

### 普通 IC (172 files)
LDO, Buck, OpAmp, DAC, Switch, Logic, LED Driver, Interface
