# OpenDatasheet 设计辅助文件包

## 目标

`data/sch_review_export/*.json` 适合 DRC 和程序消费，但硬件工程师在“拿一个器件快速搭模块”时，通常还需要更贴近原理图工作的分层文件。

`scripts/export_design_bundle.py` 就是为这个场景补的一层：把已有的器件导出再整理成**4 个面向设计的文件**，降低从 datasheet 到第一版原理图的启动成本。

如果本地同时存在 `data/extracted_v2/*.json` 与对应原始 PDF，脚本会优先补充：

- `Typical Application / Application Information`
- `Component Selection`
- `Power Supply Recommendations`
- `Layout Guidelines / Layout Example`

这些信息会进入 `L1_design_intent.json` 的 `datasheet_design_context`，以及 `L2_quickstart.md` 的设计页/公式/layout 提示。

---

## 输出层次

默认输出目录：`data/design_bundle/<MPN>/`

每个器件包含：

### `L0_device.json`

- 原始 `sch_review_export` 的完整拷贝
- 作为权威数据源保底
- 方便后续工具或脚本继续读取

### `L1_design_intent.json`

- 按原理图设计视角重组器件信息
- 包含：
  - 推荐封装 / 包信息
  - 引脚分组（电源、地、控制、状态、反馈/补偿等）
  - 关键约束（如 `vin_abs_max`、`uvlo`、`fsw`、`iout_max`）
  - 需要特别注意的引脚
  - 外围器件建议（如 `CIN`、`COUT`、`L1`、反馈分压）

### `L2_quickstart.md`

- 给硬件工程师直接看的快速设计清单
- 适合作为开图前 checklist
- 不替代 datasheet，但能把第一轮关注点提前拎出来
- 对 OpAmp 会额外总结通道数、供电方式、偏置策略、封装 pin 锚点与首选模板
对 Decoder / Deserializer 会额外总结电源 rail、参考时钟、控制总线、视频链路与首选模板

### `L3_module_template.json`

- 一个模块级起步模板
- 含占位网络、器件块、外围器件角色、待确认事项
- 对 OpAmp 额外包含 `opamp_device_context`、`package_pin_lookup`、`default_refdes_map`、`sheet_instances`、`pin_bindings`、`net_bindings`
- 适合后续映射到 KiCad / Altium / 内部原理图库工具

---

## 使用方式

### 导出单个器件

```bash
python3 scripts/export_design_bundle.py --device TPS62147
```

如果你已经把原始 PDF 放在默认目录 `data/raw/datasheet_PDF/`，脚本会直接从 PDF 页面里抽取设计提示；如果 PDF 暂时不在本地，则会退回到 `data/extracted_v2/*.json` 的页面 preview 做弱监督提取。

### 批量导出前 N 个器件

```bash
python3 scripts/export_design_bundle.py --limit 10
```

### 指定输出目录

```bash
python3 scripts/export_design_bundle.py --device GW5AT-60_UG225 --output-dir /tmp/design_bundle
```

---

## 适用场景

### 普通 IC

当前最适合这几类：

- LDO
- Buck / Boost
- 运放 / 比较器
- 视频解码器 / 反序列化器（如 MIPI CSI-2 / GMSL 桥接）
- 逻辑 / 接口芯片
- 其他带明显电源、控制、状态、反馈引脚的器件

这类器件通常能自动生成比较有用的：

- 电源输入 / 输出网络骨架
- 使能与状态信号提示
- 外围阻容感器件占位
- 引脚悬空/上下拉风险提醒

### FPGA

对 FPGA，脚本会输出更偏 bring-up 的设计骨架：

- 电源 rail 汇总
- 配置/调试接口提示
- IO / 配置 / 特殊脚分组
- JTAG/配置头预留建议

它不会替代完整 pin assignment，但能把第一版电源与配置框架先搭出来。

---

## 设计原则

- 不修改现有 `sch_review_export` 合同，避免影响下游 DRC 消费者
- 不要求立刻扩 schema 或批量重导已有导出
- 先把“设计起步层”从“审核知识层”旁边补出来
- 后续可以继续把 Application / Typical Circuit / Component Selection 页面抽取进 `L1` / `L3`

---

## 后续建议

如果要把这条能力继续做深，建议按下面顺序推进：

1. 从 datasheet 的 `Typical Application / Design Guide` 页面提取外围器件推荐值
2. 把 `L3_module_template.json` 对接到 KiCad / Altium 模板生成器
3. 增加不同拓扑的专用模板（Buck、LDO、运放、I2C 上拉、FPGA 供电树）
4. 让 bundle 反向喂给 sch-review，形成“设计前建议 + 设计后校验”的闭环
