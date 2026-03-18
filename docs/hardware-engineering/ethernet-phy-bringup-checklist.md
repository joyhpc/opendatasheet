# 以太网 PHY Bring-up 清单

## 适用场景

适用于：

- 10/100/1000BASE-T PHY
- MAC + PHY 板级接口
- RJ45 外部网口
- RGMII / RMII / GMII 到 PHY 的 bring-up

## 不适用场景

不适用于只做交换芯片软件配置或高层网络协议调试。本文针对的是板级 PHY 能否稳定起链。

## 典型失效症状

PHY 板级问题常见表现：

- `MDIO` 能访问，但始终不上链
- 某些网线、某些交换机正常，某些不稳定
- 速率协商异常，固定在低速
- `RGMII` 数据看起来在跳，但包大量错误
- 冷启动和热启动表现不一致

## 先看什么

不要一开始就抓软件网络栈。先看：

1. 主时钟和复位
2. strap 采样状态
3. `MDIO` 基本可访问性
4. 线侧磁性件、中心抽头和保护结构

## 必查顺序

### 1. 时钟与复位

- 25 MHz / 50 MHz / 125 MHz 主时钟是否稳定且匹配模式。
- 复位脉宽、释放时刻、与供电稳定时间是否满足手册。
- 是否存在时钟有了但复位一直没正确释放的情况。

### 2. Strap 与模式

- strap 电阻值是否正确。
- 更关键的是，上电采样窗口内 strap 电平是否真的成立。
- `RGMII` 延迟、PHY 地址、模式配置是否与系统假设一致。

### 3. `MDIO` 最小闭环

- 是否能稳定读出 PHY ID。
- 基本状态寄存器是否和硬件现象一致。
- 如果 `MDIO` 不通，先不要讨论线侧问题。

### 4. 线侧与磁性件

- 变压器、中心抽头供电、Bob-Smith、ESD、共模件是否按参考设计实现。
- RJ45 屏蔽壳、机壳地和数字地策略是否一致。
- 差分线对和连接器周边是否有明显布线或保护错误。

### 5. MAC 到 PHY 接口

- `RGMII/RMII/GMII` 电平、时钟、延迟策略是否一致。
- 延迟是在 PHY 内部加、MAC 内部加还是板上加，必须说清楚。
- 不能存在三处都加或三处都不加的模糊状态。

## 硬规则

- `MDIO` 未打通前，不讨论更高层网络问题。
- strap 不只看阻值，还要看采样窗口。
- 线侧磁性件和中心抽头供电必须按参考设计实现，不接受“看起来差不多”。
- `RGMII` 延迟策略必须唯一且明确。
- RJ45 外壳、机壳地、保护地、数字地关系不清，EMI 和 ESD 问题迟早出现。

## 常见失误

- strap 电阻值对了，但上电窗口错了。
- 只看 PHY 核心供电电压，不看模拟 rail 噪声和时钟质量。
- RGMII 延迟配置在 PHY、MAC、板上三者之间说不清。
- `MDIO` 通了就以为硬件没问题，忽略线侧参考设计偏差。

## 仓库入口

- 硬件文档总入口：[`index.md`](index.md)
- 相关接口主题：[`usb2-protection-and-routing.md`](usb2-protection-and-routing.md)
- 来源矩阵：[`best-practice-reference-matrix.md`](best-practice-reference-matrix.md)

## 官方参考

- 各 PHY 厂商 datasheet / hardware design guide / reference schematic
- 具体器件的 strap timing、RGMII delay、magnetics 和 layout 推荐
