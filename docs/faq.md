# OpenDatasheet FAQ

## 1) 第一次进入仓库，应该先看哪里？

如果你是第一次接触这个仓库，建议按下面顺序看：

1. `README.md` — 仓库概览、快速入口、检查命令
2. `GUIDE.md` — 阅读路径和主要文档导航
3. `docs/index.md` — 按主题和角色分类的文档索引

如果你只想快速知道“我是贡献者 / 集成者 / 维护者该看什么”，也可以直接看：
- `README.md` 里的 `Who Should Read What?`
- `docs/index.md` 里的 `Role Quick Reference`

## 2) 我应该怎么确认本地环境是健康的？

优先使用仓库已经提供的入口：

```bash
python3 scripts/doctor.py --dev
./scripts/run_checks.sh
```

推荐顺序：
- `python3 scripts/doctor.py --dev`：检查 Python、依赖、关键路径、环境变量
- `./scripts/run_checks.sh`：跑语法检查、schema 校验、回归、pytest

## 3) 我只想跑最关键的检查，最少需要跑什么？

最小建议是：

```bash
python3 scripts/validate_exports.py --summary
python3 test_regression.py
python3 -m pytest -q
```

如果你只想“一次跑完”，直接用：

```bash
./scripts/run_checks.sh
```

## 4) 什么时候需要重导出 `data/sch_review_export/`？

当改动影响以下内容时，通常需要重导出：
- `pipeline.py`
- `pipeline_v2.py`
- `scripts/export_for_sch_review.py`
- `schemas/sch-review-device.schema.json`
- `data/extracted_v2/` 中作为导出输入的内容
- 导出字段整形、归一化、消费者契约语义

典型命令：

```bash
python3 scripts/export_for_sch_review.py
python3 scripts/validate_exports.py --summary
python3 test_regression.py
```

如果只是文档、模板、CI、支持说明、仓库卫生类改动，通常**不需要**重导出。

## 5) 为什么 validator 现在同时接受 `sch-review-device/1.0` 和 `1.1`？

当前仓库处在迁移窗口：
- 当前 schema 文档目标是 `sch-review-device/1.1`
- 新生成的导出应写成 `1.1`
- 仓库里仍保留部分历史 `1.0` 产物，因此 validator 仍兼容两者

这能避免在没有进行明确重导出批次前，把历史文件全部判为无效。

如果你在做维护或发布决策，建议同时看：
- `docs/maintenance.md`
- `RELEASE.md`
- `MAINTAINERS.md`

## 6) support、bug、feature、security 应该怎么分流？

可以按这个规则判断：
- **不会用 / 不知道入口 / 本地环境问题** → `SUPPORT.md`
- **仓库行为坏了、可复现回归** → bug report
- **想加能力或改进流程** → feature request
- **密钥泄露、漏洞、可利用风险** → `SECURITY.md`

安全问题不要公开发 issue / PR，优先走 `SECURITY.md` 里的私下报告路径。

## 7) 我是下游集成者，最应该看哪几个文件？

建议优先看：
- `docs/sch-review-integration.md` — 字段语义和使用方式
- `schemas/sch-review-device.schema.json` — 正式 schema
- `data/sch_review_export/` — 实际导出样例

如果你还想理解为什么字段这样设计，再补看：
- `docs/design-document.md`
- `docs/Q3-pin-schema-design.md`

## 8) 我是维护者或 reviewer，什么情况下要停下来升级成架构讨论？

如果出现以下情况，通常不应当作“轻量改动”直接推进：
- 要移除 `1.0` 兼容
- 要改 schema 语义，而不仅是文字说明
- 要改变 `normal_ic` / `fpga` 的概念模型
- 要让下游消费者同步改代码
- 要做语义性的大规模重导出
- 要调整失败策略、数据层边界或入口模型

这类情况建议看：
- `docs/maintenance.md`
- `RELEASE.md`
- `MAINTAINERS.md`

## 9) 有没有一页纯命令速查？

有，直接看：
- `docs/commands.md`

它把 setup / doctor / checks / export / tests / release 都整理成了可复制命令。
