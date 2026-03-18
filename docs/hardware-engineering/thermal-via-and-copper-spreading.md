# 散热过孔与铺铜扩热

## 适用场景

适用于：

- 带 exposed pad 的 QFN / PowerPAD / DFN 器件
- LDO、DC/DC、LED 驱动、功率放大器
- 高功耗 FPGA / SoC / PHY 的局部热点散热

## 不适用场景

不适用于把“多打点过孔”当作通用答案的场景。热设计必须同时看热路径、焊接工艺和噪声回流。

## 典型失效症状

热过孔和铺铜做得不对，常见表现是：

- 结温高于预期，热成像显示热堆积明显
- 样板焊接空洞大、器件偏移或锡量异常
- 功率器件电气正常，但热裕量极差
- 同一器件在不同板厂或钢网条件下装配一致性差
- 为了散热扩了大铜，结果把噪声和回流问题一并放大

## 先看什么

先看三件事：

1. 热源的主散热路径到底是什么。
2. exposed pad 是否真的把热导进了连续铜面。
3. 过孔策略是否兼顾了散热和焊接工艺。

## 必查顺序

### 1. 热路径

- 热是往哪块铜、哪层、哪片散热器或哪面板外壳走的。
- 是否只有“看起来面积很大”的铜，而没有真正连接到热焊盘。
- 相邻热源是否互相叠加。

### 2. Exposed pad 与过孔

- exposed pad 是否接到足够面积的铜面。
- 热过孔是否放在真正有热流的区域，而不是离热源很远。
- 是否需要塞孔、盖孔或其它控锡策略以避免焊锡流失。

### 3. 工艺与噪声

- 钢网开窗和空洞控制是否匹配热焊盘设计。
- 热扩展铜是否与高 di/dt 回流或敏感模拟地冲突。
- 强制风冷和自然对流下，铜面策略是否合理。

## 硬规则

- 热过孔和铺铜必须服务真实热路径，不服务视觉满足感。
- Exposed pad 器件优先保证焊盘到连续铜面的热连接。
- 过孔策略必须同时考虑散热和 SMT 工艺。
- 散热铜不能无脑并入噪声严重的大电流回路。
- 如果热设计无法落到封装、钢网和板厂能力上，纸面热阻计算没有意义。

## 常见失误

- 只增加铜皮面积，却没把热从焊盘有效导出。
- 热过孔很多，但离热源太远。
- 没有控锡策略，焊锡通过过孔流失。
- 为了散热把模拟地和功率地强绑在一起。

## 仓库入口

- 硬件文档总入口：[`index.md`](index.md)
- 相关主题：[`manufacturing-dfm-quick-check.md`](manufacturing-dfm-quick-check.md)
- 来源矩阵：[`best-practice-reference-matrix.md`](best-practice-reference-matrix.md)

## 官方参考

- ADI: [`AN-1142: Techniques for High Speed ADC PCB Layout`](https://www.analog.com/media/en/technical-documentation/application-notes/an-1142.pdf)
- ADI: [`HFAN-08.1: Thermal Considerations of QFN and Other Exposed-Paddle Packages`](https://www.analog.com/cn/resources/technical-articles/2022/07/16/07/27/hfan081-thermal-considerations-of-qfn-and-other-exposedpaddle-packages.html)
- TI: [`PowerPAD Layout Guidelines`](https://www.ti.com/lit/an/sloa120/sloa120.pdf)
