# TASKS — 主控看板

> 由主控架构师维护，记录所有活跃 Worker Agent 的分支、文件边界与任务状态。

## 项目架构概要

| 层级 | 关键路径 | 说明 |
|------|---------|------|
| 入口 | `pipeline.py`, `pipeline_v2.py` | PDF 数据提取管线 v1 / v2（Gemini Text+Vision） |
| 批处理 | `batch_all.py`, `batch_ti.py`, `process_one.py` | 批量 / 单文件调度 |
| 设计提取 | `design_info_utils.py` | 正则 + 规则提取原理图设计信息 |
| 提取模块 | `extractors/` | **Phase 1 新增** — 域驱动提取模块框架 |
| 脚本工具 | `scripts/` | 导出、校验、解析（pinout / design bundle / sch review） |
| 数据模式 | `schemas/` | JSON Schema 定义（1.1 + 2.0 双版本） |
| 测试 | `test_*.py`（17 个） | pytest 覆盖管线、导出、DRC、pin 提取、extractor 框架等 |
| 数据 | `data/` | raw PDF → extracted JSON → export bundles |
| 文档 | `docs/` | 设计文档、FAQ、roadmap |
| CI | `.github/workflows/ci.yml` | GitHub Actions |
| 依赖 | PyMuPDF, httpx, google-genai, jsonschema, openpyxl | `requirements.txt` |

## Phase 1: Foundation + Register POC

### 执行波次

| Wave | Worker | 任务 | 分支 | 修改文件边界 | 状态 |
|------|--------|------|------|-------------|------|
| 1 | Worker-1 | Schema 2.0 Evolution | `phase1/schema-v2` | `schemas/` | ✅ 已合入 |
| 1 | Worker-2 | Extractor Framework + Domain Migration | `phase1/extractor-framework` | `extractors/` (新), `pipeline_v2.py` | ✅ 已合入 |
| 2 | Worker-3 | Register Extraction POC | `phase1/register-module` | `extractors/register.py` | ✅ 已合入 |
| 2 | Worker-4 | Export & Profile Adaptation | `phase1/export-adapt` | `scripts/export_*.py`, `scripts/validate_*.py` | ✅ 已合入 |
| 3 | Worker-5 | Test Suite & CI Update | `phase1/test-update` | `test_*.py`, `scripts/run_checks.sh` | ✅ 已合入 |

## Phase 2: Timing + Power Sequence

### 执行波次

| Wave | Worker | 任务 | 分支 | 修改文件边界 | 状态 |
|------|--------|------|------|-------------|------|
| 1 | Worker-6 | Timing Extraction Module | `phase2/timing-module` | `extractors/timing.py`, `schemas/domains/timing.schema.json` | ✅ 已合入 |
| 1 | Worker-7 | Power Sequence Extraction Module | `phase2/power-seq-module` | `extractors/power_sequence.py`, `schemas/domains/power_sequence.schema.json` | ✅ 已合入 |
| 2 | Worker-8 | Schema + Export + Test Integration | `phase2/integration` | `extractors/__init__.py`, `schemas/sch-review-device.schema.json`, `scripts/export_*.py`, `test_*.py`, `scripts/run_checks.sh` | ✅ 已合入 |

### 已完成任务

## Phase 3: Parametric + Selection Profile

### 执行波次

| Wave | Worker | 任务 | 分支 | 修改文件边界 | 状态 |
|------|--------|------|------|-------------|------|
| 1 | Worker-9 | Parametric Extraction Module | `phase3/parametric-module` | `extractors/parametric.py`, `schemas/domains/parametric.schema.json` | ✅ 已合入 |
| 1 | Worker-10 | Selection Profile Export | `phase3/selection-profile` | `scripts/export_selection_profile.py` (新), `data/selection_profile/` | ✅ 已合入 |
| 2 | Worker-11 | Integration + Tests | `phase3/integration` | `extractors/__init__.py`, `schemas/sch-review-device.schema.json`, `scripts/export_for_sch_review.py`, `scripts/run_checks.sh`, `test_*.py` | ✅ 已合入 |

### 已完成任务

| # | 分支 | 合并 Commit | 摘要 |
|---|------|------------|------|
| W1 | `phase1/schema-v2` | `cae95b8` | Schema 2.0 + 域子 schema |
| W2 | `phase1/extractor-framework` | `feb2c73` | Extractor 框架 + 4 域迁移 |
| W3 | `phase1/register-module` | `e4934af` | Register 提取 POC |
| W4 | `phase1/export-adapt` | `2a5b69d` | 导出层双格式适配 |
| W5 | `phase1/test-update` | `206643a` | 测试套件 + CI 更新 |
| W6 | `phase2/timing-module` | `684d921` | Timing 提取模块 |
| W7 | `phase2/power-seq-module` | `2009ef9` | Power Sequence 提取模块 |
| W8 | `phase2/integration` | `63a3c03` | Phase 2 集成 (timing + power_seq) |
| W9 | `phase3/parametric-module` | `bb366d6` | Parametric 提取模块 (后处理) |
| W10 | `phase3/selection-profile` | `0577aad` | Selection Profile 导出 (174 器件) |
| W11 | `phase3/integration` | `2a48bb2` | Phase 3 集成 (8 extractors + 80 tests) |
| W12 | `phase4/protocol-schema` | `236bea9` | Protocol 域 schema (16 协议类型) |
| W13 | `phase4/protocol-module` | `51ad148` | Protocol 提取模块 (Gemini Vision) |
| W14 | `phase4/integration` | `73130f4` | Phase 4 集成 (9 extractors + 35 tests) |
| W15 | `phase5/package-schema` | `31e9398` | Package 域 schema (36 封装类型) |
| W16 | `phase5/package-module` | `8c10ba1` | Package 提取模块 (Gemini Vision) |
| W17 | `phase5/integration` | merged | Phase 5 集成 (10 extractors + 79 tests) |

---

_最后更新：2026-03-09_

## Phase 4: Protocol Extraction

### 执行波次

| Wave | Worker | 任务 | 分支 | 修改文件边界 | 状态 |
|------|--------|------|------|-------------|------|
| 1 | Worker-12 | Protocol Domain Schema | `phase4/protocol-schema` | `schemas/domains/protocol.schema.json` | ✅ 已合入 |
| 1 | Worker-13 | Protocol Extraction Module | `phase4/protocol-module` | `extractors/protocol.py` | ✅ 已合入 |
| 2 | Worker-14 | Integration + Tests | `phase4/integration` | `extractors/__init__.py`, `schemas/sch-review-device.schema.json`, `scripts/export_for_sch_review.py`, `scripts/run_checks.sh`, `test_*.py` | ✅ 已合入 |

## Phase 5: Package / Mechanical

### 执行波次

| Wave | Worker | 任务 | 分支 | 修改文件边界 | 状态 |
|------|--------|------|------|-------------|------|
| 1 | Worker-15 | Package Domain Schema | `phase5/package-schema` | `schemas/domains/package.schema.json` | ✅ 已合入 |
| 1 | Worker-16 | Package Extraction Module | `phase5/package-module` | `extractors/package.py` | ✅ 已合入 |
| 2 | Worker-17 | Integration + Tests | `phase5/integration` | `extractors/__init__.py`, `schemas/sch-review-device.schema.json`, `scripts/export_for_sch_review.py`, `scripts/run_checks.sh`, `test_*.py` | ✅ 已合入 |
