# OpenDatasheet 设计文档

## 1. 项目定位

OpenDatasheet 是一个 **AI 驱动的电子元器件 Datasheet 参数提取引擎**，将 PDF datasheet 转化为机器可读的结构化数据，为下游的原理图审核（sch-review）、元器件选型、BOM 校验等工具提供数据基座。

**一句话概括**: PDF → 结构化 JSON → 原理图 DRC 知识库。

---

## 2. 为什么需要这个项目

### 问题

硬件工程师做原理图审核时，需要反复翻阅 datasheet 核对：
- 这个 pin 是输入还是输出？
- VIN 最大能承受多少伏？
- FB 的参考电压是多少？用来反算输出电压对不对？
- FPGA 这个 Bank 支持哪些 IO 标准？VCCO 该接多少伏？

这些信息散落在几十份 PDF 里，格式各异，人工核对效率低且容易遗漏。

### 解决方案

用 VLM（Vision Language Model）批量提取 datasheet 参数，输出统一格式的 JSON，让代码引擎自动完成 80% 的机械性检查，LLM 只处理需要"工程判断"的 20%。

---

## 3. 系统架构

```
                    ┌─────────────────────────────────────────────┐
                    │              OpenDatasheet                   │
                    │                                             │
  PDF Datasheets ──►│  Pipeline v2 (Gemini Vision)                │
                    │    ├── 页面分类 (表格/文字/图片)              │
                    │    ├── 参数提取 (VLM → JSON)                 │
                    │    ├── 物理规则校验 (L2)                     │
                    │    └── PDF 原文交叉验证 (L3)                 │
                    │                                             │
  AMD Pinout TXT ──►│  FPGA Pinout Parser                        │
                    │    ├── L1: Pin ↔ Name 映射                  │
                    │    ├── L2: Pin 分类 + 必连规则               │
                    │    ├── L3: Bank 结构 (HP/HD/GTY)            │
                    │    ├── L4: 差分对自动推导                    │
                    │    └── L5: DRC 规则模板                     │
                    │                                             │
                    │  Export Layer                                │
                    │    └── 统一输出 sch-review-device/1.0 JSON   │
                    └──────────────────┬──────────────────────────┘
                                       │
                                       ▼
                    ┌─────────────────────────────────────────────┐
                    │              sch-review                      │
                    │                                             │
  OrCAD Netlist ───►│  网表解析 → DeviceInfo + NetInfo             │
                    │  语义识别 (Stage 0-6)                        │
                    │  模块审核 (Stage 7)  ◄── 读取 export JSON    │
                    │    ├── FB 分压器 Vout 计算 (用 Vref)         │
                    │    ├── 电压越限检查 (用 Vin_max)             │
                    │    ├── Pin 功能方向推断 (用 direction)        │
                    │    └── FPGA Bank/CONFIG/差分对检查            │
                    └─────────────────────────────────────────────┘
```

---

## 4. 数据流

### 4.1 普通 IC 数据流

```
PDF datasheet
    │
    ▼ pipeline_v2.py (Gemini Vision)
    │
extracted_v2/{id}_{mpn}.json          ← 原始提取结果 (含全部参数 + pin 定义)
    │
    ▼ export_for_sch_review.py
    │
sch_review_export/{MPN}.json          ← sch-review 消费格式
    包含:
    ├── packages[pkg].pins[pin_num]   → pin 功能/方向/信号类型/未用处理
    ├── absolute_maximum_ratings      → 绝对最大额定值
    ├── electrical_parameters         → 电气参数
    └── drc_hints                     → DRC 快捷查询 (Vref/Vin_max/Iout/Iq/EN阈值)
```

### 4.2 FPGA 数据流

```
AMD Pinout TXT (从 AMD CDN 下载)     DC/AC Datasheet PDF
    │                                     │
    ▼ parse_fpga_pinout.py                ▼ pipeline_v2.py
    │                                     │
extracted_v2/fpga/pinout/{pkg}.json   extracted_v2/fpga/ds922-*.json
    │                                     │
    └──────────────┬──────────────────────┘
                   ▼ export_for_sch_review.py
                   │
sch_review_export/{Device}_{Package}.json
    包含:
    ├── pins[676]                     → 每个 pin 的功能/bank/io_type/DRC规则
    ├── lookup.pin_to_name            → pin number → pin name 映射
    ├── banks[12]                     → 每个 bank 的 IO 类型/VCCO 范围
    ├── diff_pairs[172]               → IO + GT 差分对
    ├── drc_rules[8]                  → 电源完整性/CONFIG必连/VCCO一致性/...
    ├── supply_specs                  → VCCINT/VCCAUX/... 电压规格 (来自 DC datasheet)
    └── power_rails                   → 电源轨定义 (电压/容差)
```

---

## 5. 为什么这样设计

### 5.1 两种 IC 分开处理

普通 IC 的 pin 数量少（5~48 pin），功能固定，一份 PDF 就能提取完整信息。

FPGA 完全不同：
- Pin 数量大（676~900），功能由设计决定
- DC/AC datasheet 只有电气参数，没有物理 pin 映射
- Pin 映射在 AMD 的 Package Pinout File 里（机器可读 TXT）
- 需要 Bank 级别的 IO 标准兼容性检查

所以 FPGA 需要**两个数据源合并**：DC datasheet（电气参数）+ Pinout File（物理映射）。

### 5.2 Export Layer 的必要性

Pipeline 的原始输出（`extracted_v2/`）是面向"数据完整性"设计的，包含提取过程的元数据（checksum、timing、validation 结果等）。sch-review 不需要这些。

Export Layer 做三件事：
1. **裁剪**: 只保留 DRC 需要的字段
2. **重组**: 按 sch-review 的查询模式组织数据（pin_num 为 key，和 `DeviceInfo.pins` 对齐）
3. **增强**: 提取 `drc_hints`（Vref、Vin_max 等），让 sch-review 不需要遍历整个参数表

### 5.3 drc_hints 的设计意图

sch-review 的 Stage 7 做模块审核时，最常需要的就是几个关键值。与其让 Stage 7 自己从几十个参数里搜索 Vref，不如在 export 时就提取好：

```python
# 不用 drc_hints 时 — Stage 7 需要自己搜索
vref = None
for key, param in device_kb["electrical_parameters"].items():
    if "feedback" in param["parameter"].lower() or key in ("VFB", "Vref"):
        vref = param.get("typ")
        break

# 用 drc_hints 时 — 一行搞定
vref = device_kb["drc_hints"]["vref"]["typ"]
```

### 5.4 FPGA 5 层结构的设计理由

| Layer | 解决什么问题 | 数据来源 |
|-------|-------------|---------|
| L1: Pin Map | "AF1 是什么 pin？" | AMD Pinout TXT |
| L2: Classification | "哪些 pin 必须连接？PROGRAM_B 需要上拉吗？" | Pinout TXT + UG575 规则 |
| L3: Bank Structure | "Bank 64 支持 1.8V VCCO 吗？" | Pinout TXT + DS922 |
| L4: Diff Pairs | "这两个 pin 是差分对吗？" | 从 pin name 的 P/N 后缀自动推导 |
| L5: DRC Rules | "需要检查哪些规则？" | 硬件设计规范 |

分层的好处：sch-review 可以按需加载。检查电源完整性只需要 L1+L2，检查 IO 标准兼容性需要 L3，检查差分对需要 L4。

### 5.5 代码做重活，LLM 做判断

基于超级 LLM 的架构建议（Q4），我们的设计原则是：

**凡是能用 `if-else` 或图遍历表达的规则，全部交给代码。**

- 代码检查（确定性，零漏判）：pin 连接性、电压越限、VCCO 一致性、差分对完整性
- LLM 检查（语义理解）：信号命名意图、Open-Drain 上拉遗漏、退耦电容布局合理性

OpenDatasheet 的 JSON 输出服务于代码检查层。LLM 审查层只在代码发现异常后，拿到局部拓扑切片再介入。

---

## 6. 目录结构

```
opendatasheet/
├── pipeline.py                          # v0.1 文本模式提取
├── pipeline_v2.py                       # v0.2 Vision 模式提取 (主力)
├── scripts/
│   ├── parse_fpga_pinout.py             # AMD Pinout TXT → 5 层 JSON
│   └── export_for_sch_review.py         # 统一导出 sch-review 格式
├── data/
│   ├── raw/                             # 原始 PDF + FPGA pinout TXT
│   │   ├── *.pdf                        # 普通 IC datasheet (26 份)
│   │   └── fpga/
│   │       ├── *.pdf                    # FPGA DC/AC datasheet
│   │       └── pinout/*.txt             # AMD pinout 文件 (4 个封装)
│   ├── extracted_v2/                    # Pipeline 原始提取结果
│   │   ├── *.json                       # 普通 IC (26 个)
│   │   └── fpga/
│   │       ├── ds922-*.json             # FPGA DC datasheet 提取
│   │       └── pinout/*.json            # FPGA pinout 解析 (4 个)
│   └── sch_review_export/               # ★ sch-review 消费的最终输出
│       ├── {MPN}.json                   # 普通 IC (26 个)
│       └── {Device}_{Package}.json      # FPGA (4 个)
└── docs/
    ├── sch-review-integration.md        # sch-review 对接 API 文档
    └── Q1~Q4-*.md                       # 技术决策记录
```

---

## 7. 使用方式

### 7.1 新增普通 IC

```bash
# 1. 放入 PDF
cp new_device.pdf data/raw/

# 2. 运行提取 pipeline
python3 pipeline_v2.py data/raw/new_device.pdf

# 3. 导出给 sch-review
python3 scripts/export_for_sch_review.py
```

### 7.2 新增 FPGA 封装

```bash
# 1. 从 AMD CDN 下载 pinout 文件
# URL 格式: https://download.amd.com/adaptive-socs-and-fpgas/developer/adaptive-socs-and-fpgas/package-pinout-files/usapackages/{device}{package}pkg.txt
curl -o data/raw/fpga/pinout/xcku5pffvb676pkg.txt \
  "https://download.amd.com/adaptive-socs-and-fpgas/developer/adaptive-socs-and-fpgas/package-pinout-files/usapackages/xcku5pffvb676pkg.txt"

# 2. 解析 pinout
python3 scripts/parse_fpga_pinout.py

# 3. 导出给 sch-review
python3 scripts/export_for_sch_review.py
```

### 7.3 sch-review 集成

```python
import json
from pathlib import Path

EXPORT_DIR = Path("opendatasheet/data/sch_review_export")

# 加载器件知识库
def load_device_kb(mpn, package=None):
    name = f"{mpn}_{package}" if package else mpn
    safe = name.replace("/", "_").replace(" ", "_")
    path = EXPORT_DIR / f"{safe}.json"
    return json.loads(path.read_text()) if path.exists() else None

# 使用示例
kb = load_device_kb("XL4003")
vref = kb["drc_hints"]["vref"]["typ"]           # 0.8V
vin_max = kb["drc_hints"]["vin_abs_max"]["value"]  # 35V
pin2 = kb["packages"]["TO252-5L"]["pins"]["2"]     # FB pin

fpga = load_device_kb("XCKU3P", "FFVB676")
pin_name = fpga["lookup"]["pin_to_name"]["AF1"]    # MGTYRXN0_224
bank64_vcco = fpga["banks"]["64"]["supported_vcco"] # [1.0, 1.2, 1.35, 1.5, 1.8]
```

详细 API 见 [sch-review-integration.md](sch-review-integration.md)。

---

## 8. 当前覆盖范围

| 类别 | 数量 | 示例 |
|------|------|------|
| LDO | 6 | RT9193, AMS1117, LT1964 |
| Buck | 1 | XL4003 |
| Switch | 7 | ADG714, FST3125, FUSB340 |
| Logic | 4 | 74LVC2G34, NC7SV126 |
| FPGA | 4 封装 | XCKU3P (FFVA676/FFVB676/FFVD900/SFVB784) |
| Other | 8 | AD9845B, SGM3204, LM358 |
| **合计** | **30** | |

---

## 9. 质量保证

### Pipeline 校验 (提取阶段)
- L2 物理规则校验: min ≤ typ ≤ max 单调性
- L3 PDF 原文交叉验证: 提取值与 PDF 文本比对

### Pinout 回归测试 (14 项)
- Pin 数量精确匹配封装规格
- Raw TXT ↔ JSON 逐 pin 1:1 对应
- IO diff pair 数学验证: L-pins = pairs × 2, L + T = total IO
- CONFIG DRC 100% 覆盖
- Bank 结构一致性

### Export 集成测试 (10 项)
- Pin number 查询与 sch-review DeviceInfo.pins 对齐
- Vref 可用于 FB 分压器计算
- Vin_abs_max 可用于过压检查
- FPGA pin/bank/diff_pair/supply_spec 完整性
- 跨器件电压检查可行性验证

---

## 10. 后续规划

1. **扩大覆盖**: 导入公司完整物料库的 datasheet
2. **MPN 模糊匹配**: 处理 BOM 中型号变体 (RT9193-33PB → RT9193)
3. **增量更新**: datasheet 修订时只重新提取变更页
4. **Datasheet Note 提取**: 非结构化的设计注意事项 (如 "未使用 GT 时需通过 10kΩ 接地")
5. **更多 FPGA 系列**: Artix UltraScale+, Zynq, Versal
