# 原始源文件存储规范

## 目标

`data/raw/` 存的是**可复现解析链的原始源文件**，不是提取结果。

这里的“原始源文件”包括：

- `pdf`：datasheet、package/pin guide、design guide、reference design
- `xlsx/xls`：pinout 手册、器件选型表、结构化表格源
- `csv`：结构化 pin 表、官方导出表

目标只有两个：

1. 后续任何人都能知道“某个提取结果是从哪个原件来的”
2. 同一物料同一性质文件只保留一个 canonical 原件，避免重复、漂移和版本混乱

---

## 推荐目录分层

### `data/raw/datasheet_PDF/`

- 普通器件 canonical PDF
- 由 `scripts/organize_datasheet_pdfs.py` 维护一料一类一份 canonical

### `data/raw/datasheet_PDF/_duplicates/`

- 非 canonical 的重复版本、旧版本、抓取冗余
- 不作为默认解析输入

### `data/raw/fpga/`

- FPGA 厂商级原始源
- 例如：
  - family datasheet
  - pinout xlsx/pdf
  - package & pin guide
  - schematic/design guide
  - devboard reference

### `data/raw/_staging/`

- 新下载但还没定版的临时源
- 不应作为正式解析输入
- 经过确认后再移动到正式目录

---

## canonical 规则

- 同一物料、同一文档性质，只保留一个 canonical 原件
- canonical 文件必须放在**非 `_` 前缀目录**中
- `_duplicates/` 里的文件允许保留，但默认不进入解析主链
- `_staging/` 里的文件不允许视为正式源
- 文件名优先保留厂家原名，不额外“人肉改名”

---

## 什么是 manifest

`manifest` 可以理解成“原始源文件清单 / 索引表”。

它**不是文件内容本身**，而是描述这些文件的目录账本。至少会记录：

- 文件放在哪里
- 是 `pdf/xlsx/csv` 哪一种
- 它是 datasheet、pinout，还是 package guide
- 它是 canonical、duplicate，还是 staging
- 文件大小
- 文件哈希（`sha256`）

这样做的价值是：

- 能快速回答“这个器件当前到底有哪些原始源”
- 能判断“现在解析用的是不是同一份原件”
- 能避免重复下载、重复提交、同名不同版本混用
- 别的 agent 可以直接读取 manifest，不用全盘乱扫

可以把它理解成图书馆目录卡，而不是书本本身。

---

## manifest 文件位置

默认使用：

- `data/raw/_source_manifest.json`

由下面脚本生成：

```bash
python3 scripts/build_raw_source_manifest.py
```

校验 manifest 是否过期：

```bash
python3 scripts/build_raw_source_manifest.py --check
```

---

## manifest 字段说明

每条 entry 目前包含：

- `path`：相对 `data/raw/` 的路径
- `filename`：原始文件名
- `format`：`pdf/xlsx/xls/csv`
- `doc_type`：`datasheet/pinout/package_guide/design_guide/reference/app_note/unknown`
- `storage_tier`：`canonical/duplicate/staging/archive`
- `source_group`：顶层分组，如 `datasheet_PDF`、`fpga`
- `vendor_hint`：从路径/文件名推测出的厂商
- `family_hint`：从文件名推测出的家族/系列，如 `GW1N`、`GW5AT-60`
- `material_hint`：用于快速检索的物料/系列提示
- `size_bytes`：文件大小
- `sha256`：文件内容哈希

---

## 入库建议流程

1. 新文件先放 `data/raw/_staging/`
2. 判断文档性质：datasheet / pinout / package guide / design guide / reference
3. 如果是正式使用版本，移动到对应正式目录
4. 如果发现旧版本或重复版本，放入 `_duplicates/`
5. 执行：

```bash
python3 scripts/build_raw_source_manifest.py
```

6. 若涉及 PDF canonical 选择，再执行：

```bash
python3 scripts/organize_datasheet_pdfs.py
```

---

## 当前约束

- 没有进 manifest 的原始源，不算“正式受管控输入”
- 新 parser 尽量只消费 canonical 文件
- 同一物料不要同时出现多个相同性质的 canonical 文件
- 如果需要改 PDF 解析策略，先固定原始源，再做强验证和闭环测试
