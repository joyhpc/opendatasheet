# GW5AT & GW5AST 系列 FPGA 原理图设计指南
# Source: UG984-1.2

## 1. 电源设计

### 电源域分类
| 组 | 电源 | 说明 |
|---|------|------|
| FPGA | VCC | 核电压 |
| FPGA | VCCX | 辅助电压 |
| FPGA | VCCIO | I/O Bank 电压 |
| FPGA | VCCLDO | 内部 LDO 模块电源（为 SRAM 和 PLL 供电） |
| SerDes | VDDAQ* | QUAD* 模拟电路供电 |
| SerDes | VDDDQ* | QUAD* 数字电路供电 |
| SerDes | VDDHAQ* | QUAD* 高压供电 |
| SerDes | VDDTQ* | QUAD* TX 发送端供电 |
| MIPI | VDDAM | 模拟电路供电 |
| MIPI | VDDDM | 数字电路供电 |
| MIPI | VDDXM | 辅助供电 |

### 上电顺序与斜率
- **推荐 VCCX 在 VCC 之前上电**
- VCC 上升斜率: 0.1 ~ 15 mV/us
- VCCLDO 上升斜率: 0.09 ~ 15 mV/us
- VCCX 上升斜率: 0.005 ~ 15 mV/us
- VCCIO 上升斜率: 0.06 ~ 15 mV/us

### 电源合并建议
| 电源 | 建议 |
|------|------|
| VCC | 电流大，**建议单独供电** |
| VCCX | 满足电流需求下，可与同电压电源合并 |
| VCCLDO | 满足电流需求下，可与同电压电源合并 |
| VDDAQ0/Q1 + VDDDQ0/Q1 | 电压一致可合并，**建议用低噪声电源（LDO）** |
| VDDHAQ0/Q1 | 电压一致可合并 |
| VDDTQ0/Q1 | 可合并，但**噪声大，不要和其他电源合并** |
| VDDAM + VDDDM | 满足电流需求下可合并 |
| VDDXM | 满足电流需求下可合并 |

### 隔离滤波
- 各电压域之间需要磁珠隔离滤波
- 磁珠 + 陶瓷电容（精度 ≤ ±10%）
- 电源合并时建议用磁珠隔离

### 纹波要求
- VCC: ≤ 3%
- VCCIO: ≤ 5%
- VCCX: ≤ 5%
- VCC 纹波影响 PLL 输出时钟抖动
- VCCIO 纹波传递到 IO Buffer 输出波形

## 2. 关键配置管脚

### RECONFIG_N
- 低电平有效，相当于配置复位
- 上电过程中**务必保持高电平**
- 上电稳定 1ms 后可释放
- 重配置需要 ≥25ns 低电平脉冲
- 作为 GPIO 时只能用作 output

### READY
- 高电平有效，READY 拉高时才能配置
- 开漏输出，**需要外部 4.7K 上拉到 3.3V**

### DONE
- 配置成功标志，成功后拉高
- 开漏输出，**需要外部 4.7K 上拉到 3.3V**
- 作为 GPIO input 时需保证配置前初始值为 1

### CFGBVS（配置 Bank 电压选择）
- 配置 IO 所在 Bank (bank3, bank4, bank10) 的 VCCIO ≥ 2.5V → CFGBVS 接高
- 配置 IO 所在 Bank 的 VCCIO ≤ 1.8V → CFGBVS 接低
- **必须设置，不能悬空**

### PUDC_B（配置期间上拉控制）
- 低电平: 配置期间所有 GPIO 弱上拉
- 高电平: 配置期间所有 GPIO 高阻
- **不允许悬空**，通过 1kΩ 电阻接 VCCIO 或 GND

### MODE[2:0]
- 配置模式选择
- 上拉电阻推荐 4.7K，下拉电阻推荐 1K
- 未封装出来的 MODE 管脚内部已接地或接电源
- **程序加载成功后自动切到 SSPI 模式**
- 如果不用 SSPI，需要 SSPI_HOLDN 下拉或 SSPI_CSN 上拉

## 3. 配置模式

### GW5AT-15 支持的配置模式
| 封装 | JTAG | MSPI | SSPI | Slave Serial | Slave CPU |
|------|------|------|------|-------------|-----------|
| CS130 | ✓ | ✓ | ✓ | ✓ | ✓ |
| CS130F | ✓ | ✓ | ✓ | ✓ | ✓ |
| MG132 | ✓ | ✓ | ✓ | ✓ | ✓ |

### JTAG
- 时钟频率**不能高于 100MHz**
- VCCIO 保持与 JTAG 信号所在 Bank 电压一致
- 建议加 ESD 保护（SP3003_04XTG）
- TCK 需要 4.7K 上拉到 VCCIO + 0.1uF 去耦

### MSPI (Master SPI)
- FPGA 作为主器件，从外部 Flash 读取比特流
- 支持 x1/x2/x4 模式
- 信号: CCLK(输出), MCS_N, MOSI, MISO, WP, HOLD

### SSPI (Slave SPI)
- FPGA 作为从器件
- 信号: SSPI_CLK(输入), SSPI_CSN, SSPI_SI, SSPI_SO, SSPI_HOLDN, SSPI_WPN
- 支持多 FPGA 级联配置

## 4. 时钟设计

### 时钟资源
- GCLK: 8 时钟域，每域 16 个 GCLK 网络
- HCLK: 高速时钟，支持源同步数据传输
- PLL: 倍频/分频/相位/占空比调整
- DQS: DDR 存储器接口时钟

### 设计注意事项
- SerDes 高速时钟: **靠近 FPGA 管脚处串联 0.1uF 电容**
- 系统时钟: 单端输入建议从 GCLK_T 端输入
- PLL 时钟输入: 建议从专用 PLL 管脚输入，单端从 PLL_T 端
- 外接晶振: 磁珠(MH2029-221Y) + 10nF 去耦 + 电阻(精度 ≤ ±5%)

## 5. 差分管脚

### LVDS
- GW5AT-15 和 GW5AT-60: **所有分区支持片内可编程 100Ω 输入差分匹配电阻**
- GW5AT-138/75: 仅 Top/Bottom 分区支持
- 单端电阻: SSTL/HSTL 输入输出
- 差分电阻: LVDS/PPDS/RSDS 输入

## 6. 管脚分配注意事项
- 所有 Bank 都支持真 LVDS 输出
- SSTL/HSTL 需要 VREF（可用内置 0.5*VCCIO 或外部输入）
- DDR 管脚分配参考 TN662

## 7. GW5AT-15 封装对比（来自 UG983-1.2.8）

| 参数 | MG132 | CS130 | CS130F |
|------|-------|-------|--------|
| 类型 | UBGA | CSP | CSP Flip-chip |
| 尺寸 | 8×8mm | 4.0×5.3mm | 4.0×5.3mm |
| 间距 | 0.5mm | 0.35mm | 0.35mm |
| 总 IO | 53 | 53 | 53 |
| 差分对 | 25 | 25 | 25 |
| True LVDS | 25 | 25 | 25 |
| VCC pins | 8 | 4 | 4 |
| VCCX pins | 3 | 0 (合并) | 0 (合并) |
| VSS pins | 11 | 11 | 11 |
| Bank 1 IO | 30 | 30 | 30 |
| Bank 2 IO | 7 | 7 | 7 |
| Bank 3 IO | 8 | 8 | 8 |
| Bank 4 IO | 8 | 8 | 8 |

注: CS130/CS130F 的 VCCX、VCCLDO、VDDXM 合并为同一管脚
