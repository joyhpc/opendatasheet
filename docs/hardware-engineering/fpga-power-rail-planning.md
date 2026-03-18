# FPGA 电源轨规划

## 适用场景

适用于：

- AMD/Xilinx FPGA
- Intel FPGA / SoC FPGA
- Lattice / Gowin FPGA
- 带 DDR、SerDes、高速 IO 的中高复杂度 FPGA 板卡

## 不适用场景

不适用于只想给一个小 CPLD 拉一条 3.3 V 电源的简单设计。本文面向的是多 rail、时序敏感、噪声敏感的 FPGA 电源系统。

## 典型失效症状

FPGA 电源规划没做好，现场通常表现为：

- rail 电压看起来都对，但配置偶发失败
- IO 某些模式下正常，满载或高速模式下异常
- 热态、边界工况或高并发接口时随机失效
- DDR / transceiver 链路不稳，但数字逻辑本身正常
- bring-up 初期似乎可用，后续加功能后问题集中暴露

## 先看什么

先别急着看某一颗 regulator 的料号。先看：

1. rail 是否按核心、辅助、配置、bank、收发器模拟/终端分层。
2. 每条 rail 的电流预算是不是 worst-case，而不是典型值。
3. 电压容差、瞬态、启动顺序是不是和器件手册一致。
4. 去耦和 PDN 是否在 BGA 附近可实现。

## 必查顺序

### 1. rail 分类

- `VCCINT`、`VCCAUX`、`VCCBRAM`、`VCCIO`、`MGTAVCC`、`MGTAVTT` 等是否明确分开。
- 是否错误合并了模拟 rail 和数字 rail。
- 是否把多个 bank 电压粗暴并到一个通用 rail。

### 2. 电流与容差

- 是否用官方功耗工具或 worst-case 估算得出 rail 电流。
- rail 容差是否满足器件要求，而不是“看起来接近”。
- 关键 rail 是否考虑瞬态电流和并发工作模式。

### 3. 启动与控制

- 上电顺序、PG、复位、配置时序是否匹配 FPGA 手册。
- 是否存在“所有 rail 都能起来，但顺序偶发错”的风险。
- 是否有掉电反灌或跨域残余供电问题。

### 4. PDN 与去耦

- 去耦是否有近端高频 + 分布式 bulk 的分层策略。
- BGA 周边是否有足够落地空间支撑所需电容密度。
- 电源入口到核心供电球之间是否存在明显瓶颈。

## 硬规则

- FPGA 电源不能只按平均功耗规划。
- 模拟 rail、bank rail、核心 rail 不能只因电压相近就合并。
- `VCCIO` 规划必须服务 IO 标准和 bank 划分，不允许后补。
- rail 容差、瞬态、启动顺序必须来自器件手册，不接受经验替代。
- 如果 rail 规划还没定，就不该冻结原理图。

## 常见失误

- 只按典型功耗估算，未覆盖高速 IO 或 transceiver 同时工作。
- 复制参考设计里的 rail 名称，但没复制其容差和时序假设。
- 忽略 BGA 周边去耦空间，纸面 PDN 很漂亮，板上放不下。

## 仓库入口

- 硬件文档总入口：[`index.md`](index.md)
- 相关 FPGA 主题：[`fpga-bank-voltage-planning.md`](fpga-bank-voltage-planning.md)
- 来源矩阵：[`best-practice-reference-matrix.md`](best-practice-reference-matrix.md)

## 官方参考

- Intel: [`PCB Design Guidelines: Agilex 5`](https://www.intel.com/content/www/us/en/docs/programmable/821801/current/power-distribution-network-design-guidelines-01408.html)
- Intel: [`Agilex 7 Power Distribution Network Design Guidelines`](https://www.intel.com/content/www/us/en/docs/programmable/683393/current/board-power-delivery-network-simulations.html)
- AMD/Xilinx 各 family 的 power supply / PCB design guide
