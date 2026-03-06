# OpenDatasheet Troubleshooting

> Lightweight troubleshooting guide for the most common repository failure modes.

## 1. 环境依赖缺失

### 典型现象
- `ModuleNotFoundError`
- `ImportError`
- `No module named ...`
- `python3 scripts/doctor.py --dev` 显示某个依赖是 `missing`

### 优先处理方式
先跑环境自检：

```bash
python3 scripts/doctor.py --dev
```

如果缺依赖，按当前仓库入口补齐：

```bash
./scripts/bootstrap.sh
```

或者手动安装：

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 常见原因
- 没安装 dev 依赖，导致 `pytest` / `jsonschema` 不可用
- 本地 Python 环境切换后没有重新安装依赖
- 只装了 runtime 依赖，但在跑测试或校验命令

---

## 2. `GEMINI_API_KEY` 未设置

### 典型现象
- `pipeline.py` 或 `pipeline_v2.py` 报 `Missing GEMINI_API_KEY environment variable`
- `python3 scripts/doctor.py --dev --strict-env` 失败

### 处理方式
先导出环境变量：

```bash
export GEMINI_API_KEY='<your-api-key>'
```

然后再执行需要 Gemini 的流程，例如：

```bash
python3 pipeline_v2.py <pdf-path>
```

### 说明
- 普通校验流程（例如 `./scripts/run_checks.sh`）通常不要求真的调用 Gemini
- 只有实际跑提取流程时，`GEMINI_API_KEY` 才是硬要求

---

## 3. Schema 校验失败

### 典型现象
- `python3 scripts/validate_exports.py --summary` 显示 `Failed > 0`
- 回归测试里的 `T2.2 All exports pass schema validation` 失败

### 优先排查顺序
先单独运行：

```bash
python3 scripts/validate_exports.py --summary
```

如果失败：
1. 先确认是单个已提交产物异常，还是生成逻辑整体有问题
2. 优先修生成逻辑，不要先手改大量导出 JSON
3. 修完后重新跑：

```bash
python3 scripts/validate_exports.py --summary
python3 test_regression.py
python3 -m pytest -q
```

### 当前仓库的预期状态
- validator 同时接受 `sch-review-device/1.0` 和 `sch-review-device/1.1`
- 新导出目标应为 `1.1`
- 历史 `1.0` 产物在迁移期内仍可能保留

### 什么时候要升级成更大讨论
如果失败是因为：
- 想移除 `1.0` 兼容
- schema 语义要变
- 下游消费者契约要变

这已经不是普通故障排查，应该转去看：
- `docs/maintenance.md`
- `RELEASE.md`
- `MAINTAINERS.md`

---

## 4. `pytest` 收集或执行异常

### 典型现象
- `pytest` 没有收集到预期入口
- `pytest` 收集了不该收集的脚本 helper
- `pytest` 报奇怪的 fixture / collection 错误

### 当前仓库的预期
当前仓库已经把 `pytest` 入口收敛为标准入口，正常情况下执行：

```bash
python3 -m pytest -q
```

应当通过。

如需查看收集情况：

```bash
python3 -m pytest --collect-only
```

### 排查方向
- 确认 `pyproject.toml` 里的 pytest 配置没有被破坏
- 确认脚本型测试文件没有重新出现“导入即执行”的副作用
- 确认 helper 函数命名没有被误写成 pytest 可收集入口

如果只是想跑仓库标准检查，优先用：

```bash
./scripts/run_checks.sh
```

---

## 5. 不确定当前改动是否需要重导出

### 需要重导出的常见场景
如果改动影响：
- `pipeline.py`
- `pipeline_v2.py`
- `scripts/export_for_sch_review.py`
- `schemas/sch-review-device.schema.json`
- `data/extracted_v2/` 中作为输入的数据
- 导出字段整形、归一化、消费者语义

通常需要：

```bash
python3 scripts/export_for_sch_review.py
python3 scripts/validate_exports.py --summary
python3 test_regression.py
```

### 通常不需要重导出的场景
如果只是改了：
- 文档
- CI / 模板 / issue 分流
- README / GUIDE / SUPPORT / SECURITY / FAQ
- 仓库卫生脚本或导航文档

通常**不需要**重导出。

### 快速判断规则
- 如果导出数据“含义”变了，通常要重导出
- 如果只是“协作方式”或“文档入口”变了，通常不用重导出

---

## 6. 推荐的最小恢复路径

如果你不确定从哪里开始，按下面顺序恢复：

```bash
python3 scripts/doctor.py --dev
./scripts/run_checks.sh
```

如果问题只和导出有关，再补：

```bash
python3 scripts/validate_exports.py --summary
python3 test_regression.py
```

如果问题和导出语义、schema 迁移、发布边界有关，继续看：
- `docs/maintenance.md`
- `docs/faq.md`
- `RELEASE.md`
- `MAINTAINERS.md`

---

## 7. 什么时候不要自己继续修

应停止“轻量修复”并升级讨论的情况：
- 需要改 schema 语义，不只是改文案
- 想移除 `1.0` 兼容
- 需要下游消费者一起改
- 需要大规模语义性重导出
- 需要调整 `normal_ic` / `fpga` 的概念模型

这时不应把问题继续当作普通排障处理。
