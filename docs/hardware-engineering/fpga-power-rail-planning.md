# FPGA 电源轨规划

## 适用场景

适用于 AMD/Xilinx、Intel、Lattice、Gowin FPGA 及 SoC FPGA 的板级电源规划。

## 关键规则

- FPGA 供电应按 `核心`、`辅助`、`配置`、`Bank VCCIO`、`收发器模拟/终端` 分层，不要合并成“大 1.8 V”和“大 3.3 V”。
- 先用官方功耗估算工具做 worst-case rail 电流预算，再决定 regulator 和 PDN。
- 关键 rail 要看瞬态电流和容差，不只是稳态平均电流。
- Bank rail 规划必须服务 IO 标准和接口分区，不能等 pin assignment 完成后再反推。

## 评审清单

- 每条 rail 的电压容差、瞬态要求、推荐去耦和启动约束是否明确。
- VCCINT、VCCAUX、VCCBRAM、VCCIO、MGTAVCC、MGTAVTT 等是否被混接。
- 上电顺序和电源 good 是否满足器件手册要求。
- 电源入口到 BGA 球附近是否预留足够去耦密度和回流通道。
- 电源树是否为后续功耗增长预留余量。

## 常见失误

- 只按典型设计功耗规划，未覆盖满速 IO 或高速收发器同时工作。
- 将多个 bank 绑在一个 rail 上，后期 IO 标准选择被锁死。
- 参考设计复制了 rail 名称，却没有复制容差和启动约束。
