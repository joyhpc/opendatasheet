# GW5AT-60 开发板参考设计分析
# Source: DK_START_GW5AT-LV60UG225 V1.1

## 电源拓扑

### 一级电源（12V Buck）
| 输入 | 输出 | 电流 | IC | 用途 |
|------|------|------|-----|------|
| 12V | 3.3V | 6A | TPS54620RHLR | VCCX, Bank IO (3.3V), Flash, 外设 |
| 12V | 1.5V | 6A | TPS54620RHLR | DDR3 (VCC1P5) |
| 12V | 1.2V | 6A | TPS54620RHLR | 中间电压，给 LDO 供电 |
| 12V | 2.1V | 6A | TPS54620RHLR | SerDes VDDHA (1.8V LDO 输入) |

### 二级电源（LDO）
| 输入 | 输出 | 电流 | IC | 用途 |
|------|------|------|-----|------|
| 1.2V | 0.95V | 3A | TPS7A8400ARGRR | VCC 核电压, SerDes VDDD/VDDA, MIPI |
| 2.1V | 1.8V | 3A | TPS7A8400ARGRR | SerDes VDDHA, Bank IO (1.8V) |

### DDR VTT/VREF
- TPS51200DRCR: DDR3 VTT 终端电压 (0.75V = VCC1P5/2)
- VTTREF: DDR3 参考电压

### 电源树
```
12V DC Jack
├── 3.3V/6A (TPS54620) → VCC3P3, V3P3, VCCX, Bank10/11
├── 1.5V/6A (TPS54620) → VCC1P5 (DDR3)
│   └── 0.75V (TPS51200) → DDRVTT, VTTREF
├── 1.2V/6A (TPS54620) → VCC1P2
│   └── 0.95V/3A (TPS7A8400) ×3 → V0P95-1 (VCC核/MIPI_VDDD)
│                                    V0P95-2 (SerDes VDDA_Q)
│                                    V0P95-3 (SerDes VDDD_Q)
└── 2.1V/6A (TPS54620) → VCC2P1
    └── 1.8V/3A (TPS7A8400) → VCC1P8, VCC1P8_Q (SerDes VDDHA_Q)
```

## FPGA 电源引脚分配 (UG225 封装)

### 核电压 VCC (0.95V)
- Pins: G8, J8, J10, H9, K7, F9, H7, G10, B1, K9, J6, M12, F7
- 功能: VCC/VCCC
- 去耦: 100uF×1 + 4.7uF×1 + 0.1uF×6

### IO Bank 电压 VCCIO
- VCCIO1/2: B12 → V1P8 (1.8V) — DPHY
- VCCIO3/4: D14, H14 → V1P8 (1.8V) — DDR3
- VCCIO5: J12, M14 → V3P3 (3.3V)
- VCCIO8: P8, P12 → V3P3 (3.3V)
- VCCIO9: P4, M7 → V3P3 (3.3V)
- VCCIO10/11: M2, L4 → VCC1P2 (1.2V) — MIPI

### 辅助电压 VCCX (3.3V)
- Pins: G6, B1, K9, J6, M12, F7
- 去耦: 0.1uF per pin

### SerDes 电源
- Q0_VDDHA (1.8V): D9, D7 → VDDHA_Q
- Q0_VDDD (0.95V): B4, A6 → VDDD_Q
- Q0_VDDA (0.95V): A10, B8, D11, D5 → VDDA_Q
- 去耦: 100uF×1 + 4.7uF×1 + 0.1uF×3 per group

### MIPI 电源
- MIPI_VDD12 (1.2V): G6
- M0_VDDA (0.95V): D2, H2, G4
- 去耦: 100uF×1 + 4.7uF×1 + 0.1uF×3

### ADC 电源
- VDDH_ADC: E12 → 1.8V (通过 Q0_VDDHA 内部 LDO 或共用 VDD18 平面)

### VQPS
- Pin: L11

## 配置电路

### 配置模式
- MODE[1:0] 引脚: F_MODE0, F_MODE1
- 主配置方式: MSPI (Master SPI)
- Flash: 外部 SPI Flash

### MSPI 信号
- MSPI_CS_N, MSPI_CLK, MSPI_MOSI, MSPI_MISO
- MSPI_WP (Write Protect), MSPI_HOLD

### 配置状态
- F_DONE: 配置完成指示
- F_READY: 就绪指示
- F_RECONFIG_N: 重配置触发（低有效）
- F_KEY: 加密密钥相关

### JTAG
- F_TCK, F_TDI, F_TDO, F_TMS
- USB Bridge: FT232HQ (USB to JTAG)
- ESD 保护: TPD2E001DRLR

### 时钟
- 50MHz (1.8V): F_CLK_50M → FPGA
- 200MHz 差分: F_CLK_200M_P/N → FPGA (系统主时钟)
- 135MHz: SerDes 参考时钟

## 接口电路

### DDR3
- IC: W632GU6NB-11 (Winbond 512MB DDR3)
- 16-bit 数据总线 (DQ0-DQ15)
- 电源: VCC1P5 (1.5V), DDRVTT (0.75V), VTTREF
- 终端: 49.9Ω/100Ω 串联电阻

### DisplayPort (Type-C)
- 连接器: FDL01-FSB300K6M (Type-C)
- TX: 4 lanes (DP_TX0-3)
- RX: 4 lanes (DP_RX0-3)
- AUX: DP_TX_AUX_P/N, DP_RX_AUX_P/N
- Hot Plug: DP_TX_HOT_PLUG, DP_RX_HOT_PLUG
- ESD: RClamp0524P, TPESDR0524PMUTAG

### MIPI
- C-PHY: 3 三线通道 (CPHY_A/B/C × 0/1/2)
- D-PHY TX2: 4 data lanes + 1 clock (DPHY_TX2_D0-D3, DPHY_TX2_CK)
- 硬核 MIPI

### GPIO
- F_GPIO0-3: 通用 IO
- 连接器: BK13C06-40DS (40pin FPC)

## 去耦策略总结

每组电源域标准配置:
- 大容量: 100uF (电解/钽) × 1
- 中容量: 4.7uF (MLCC) × 1
- 高频: 0.1uF (MLCC) × 3~6

VCC 核电压去耦最密集: 100uF + 4.7uF + 0.1uF×6
VCCIO 每个 Bank: 0.1uF × 2~4
SerDes 每个电源域: 100uF + 4.7uF + 0.1uF×3

## 关键设计注意事项

1. 0.95V 核电压用 3 路独立 LDO (TPS7A8400)，不共用，分别供 VCC/VDDA/VDDD
2. SerDes 电源用磁珠 (MPZ1608S101A) 隔离数字噪声
3. DDR3 VTT 用专用 sink/source LDO (TPS51200)
4. 1.8V SerDes VDDHA 从 2.1V 降压，不从 3.3V 降（减少 LDO 压差损耗）
5. VDDH_ADC 通过 Q0_VDDHA 内部 LDO 供电，不需要外部独立电源
6. 100Ω 电阻靠近 FPGA 放置（原理图注释）
