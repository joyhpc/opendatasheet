# USB 2.0 防护与走线

## 适用场景

适用于：

- USB Device
- USB Host
- USB Hub
- Type-C 口上的 USB2 D+/D- 通道
- 板边连接器或线缆引出的 USB2 接口

## 不适用场景

不适用于 USB3.x / Type-C 全功能高速通道设计。本文只针对 USB2 的 D+/D-、VBUS、CC 和入口保护。

## 典型失效症状

USB2 板级设计不对，现场通常表现为：

- 插拔后偶发不枚举
- 某些线缆能用，某些线缆不稳
- ESD 后口还活着，但主控已异常
- 设备上电正常，但插上主机后掉电或反复重连
- Type-C 口 `VBUS` 有了、`D+/D-` 也连了，但角色识别完全不对

## 先看什么

不要先抓软件日志。先看：

1. 连接器附近的保护和回流路径。
2. `D+/D-` 是否是连续、短 stub、低寄生的通道。
3. `VBUS` 是否有明确的开关、限流和浪涌策略。
4. 如果是 Type-C，`CC` 是否真的定义了角色。

## 必查顺序

### 1. 连接器入口

- ESD 器件是否紧贴连接器，而不是贴着主控。
- `D+/D-` 从连接器到保护器件之间是否仍有过长裸奔走线。
- 保护件回地是否短而直接。

### 2. `D+/D-` 通道

- 是否保持成对、短 stub、连续参考平面。
- 是否存在过大串联电阻、共模件或高电容 TVS。
- 若通过连接器、转接板或排线，是否仍满足通道连续性。

### 3. `VBUS` 路径

- 是否有电源开关、限流或过压保护，而不是直接硬连到主 5 V。
- Device、Host、Hub 的 `VBUS` 策略是否与角色一致。
- 插拔浪涌是否会直接打到后级主电源树。

### 4. Type-C 逻辑

- `CC1/CC2` 的上下拉是否正确。
- 角色定义、默认电流、`VBUS` 开关控制是否前后一致。
- 是否误把 Type-C 当作“只是换了个连接器的 USB2”。

## 硬规则

- USB 保护件必须放在入口，不是放在被保护芯片旁边。
- `D+/D-` 上不允许挂高电容、长 stub、随意测试点。
- Type-C 只接 `D+/D-` 和 `VBUS` 而不处理 `CC`，设计就是不完整的。
- `VBUS` 不能默认直接并到系统 5 V，必须解释电源方向和保护策略。
- 枚举问题如果在不同线缆和插拔条件下变化，优先怀疑板级通道而不是固件。

## 常见失误

- 保护件离连接器太远。
- Type-C 只接了 `D+/D-` 和 `VBUS`，忽略 `CC`。
- `VBUS` 入口没有限流和浪涌控制。
- 在 `D+/D-` 上加了“看起来更稳”的高电容件，结果高速边沿被拖坏。

## 评审示例

例子：

- Type-C 口作为 USB2 Device
- `D+/D-` 已连到主控
- `VBUS` 直接接系统 5 V
- `CC` 只做了机械连接，没有角色电阻
- ESD 管放在主控旁边而不是连接器旁边

正式 review 时，至少应给出：

- `ERROR`: Type-C 未定义 `CC` 角色，不应放行。
- `ERROR`: `VBUS` 直接并系统 5 V，没有明确方向和保护策略，不应放行。
- `ERROR`: ESD 器件位置错误，防护链路不成立。

如果结论只是“后续实验看看能不能枚举”，那这次 review 没抓住硬错误。

## 仓库入口

- 硬件文档总入口：[`index.md`](index.md)
- 相关接口主题：[`ethernet-phy-bringup-checklist.md`](ethernet-phy-bringup-checklist.md)
- 来源矩阵：[`best-practice-reference-matrix.md`](best-practice-reference-matrix.md)

## 官方参考

- Microchip: [`USB Device Design Checklist`](https://www.microchip.com/en-us/application-notes/an2621)
- Microchip: [`USB333x Transceiver Layout Guidelines`](https://www.microchip.com/en-us/application-notes/an204)
- Microchip: [`Implementation Guidelines for Microchip USB 2.0/3.1 Gen 1 Hub Devices`](https://ww1.microchip.com/downloads/aemDocuments/documents/UNG/ApplicationNotes/ApplicationNotes/AN26.2-Application-Note-DS00001876.pdf)
