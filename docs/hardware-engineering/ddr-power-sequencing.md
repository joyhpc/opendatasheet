# DDR 供电与时序规划

## 适用场景

适用于 DDR3/DDR4/LPDDR/DDR5 板级设计、SoC/FPGA 外挂内存设计和 bring-up 评审。

## 关键规则

- DDR 不是只有 `VDD`，还要同时审视 `VPP`、`VREF`、`VTT`、`VDDQ`、`VDDSPD` 等相关 rail。
- VREF 是参考，不是普通电源，不应承受动态负载污染。
- VTT 终端电源通常要求双向灌拉能力，不能随便用普通 LDO 代替。
- 电源时序、复位、时钟、CKE/RESET_n 必须与控制器手册对应。

## 评审清单

- 所有 DDR rail 电压和容差是否符合器件等级。
- VTT 稳压器是否支持源/灌电流并有足够瞬态性能。
- VREF 是否独立滤波并避免跨层长距离分配。
- DDR reset、clock enable、ZQ、strapping 是否满足启动时序。
- 控制器与 DRAM 的电源上电顺序是否被 PMIC 或 supervisor 真正保证。

## 常见失误

- 把 VREF 当普通 rail 使用，挂上额外负载。
- VTT 只看额定电流，不看 sink/source 对称能力。
- 只照搬参考设计值，却没有核对所选 DRAM 代际差异。
