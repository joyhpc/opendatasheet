# Automotive Video SerDes 归一化

> 这份文档定义仓库里车载视频 serializer / deserializer / bridge 器件的统一表示方式，以及新同类芯片进入仓库时的处理流程。

## 1. 为什么要单独归一

这类器件有一个共同问题：

- 厂商不同
- 链路家族不同
- pin 名不同
- 但系统角色其实很像

典型例子：

- `CXD4984ER-W`
- `MAX96718A`
- 后续的 `DS90UB*`

如果只保留原始描述，比如：

- `GVIF3 deserializer`
- `Dual GMSL2/GMSL1 to CSI-2 Deserializer`

那人能看懂，但程序很难统一消费。

所以归一化的目标不是抹平厂商差异，而是把“同一类系统角色”变成统一结构。

## 2. 统一后的核心模型

归一化后，这类器件统一落到两个层次：

### 2.1 类目层

顶层 `category` 统一为：

- `Automotive Video SerDes`

这个字段用于：

- 快速筛选
- 建立最粗颗粒度的器件集合

### 2.2 能力层

真正给下游消费的统一结构是：

- `capability_blocks.serial_video_bridge`

它表达的不是品牌，而是系统角色：

- 是不是 serializer / deserializer / aggregator
- 串行侧用什么链路家族
- 视频侧输出什么协议
- 控制面怎么进来

## 3. 标准结构

统一能力块采用下面这组字段：

```json
{
  "class": "serial_video_bridge",
  "present": true,
  "device_role": "deserializer",
  "application_domain": "automotive_camera",
  "system_path": "camera_module_to_domain_controller",
  "link_families": ["GVIF3"],
  "link_direction": "serial_in_to_video_out",
  "serial_links": {},
  "video_output": {},
  "control_plane": {},
  "source_basis": "primary_pdf_manual_profile"
}
```

字段解释：

- `device_role`
  - `serializer` / `deserializer` / `aggregator` / `bridge`
- `application_domain`
  - 表示大类应用域，例如 `automotive_camera`、`automotive_display`、`automotive_video`
- `system_path`
  - 明确器件所在系统路径
  - 当前优先使用：
    - `camera_module_to_domain_controller`
    - `domain_controller_to_display`
- `link_families`
  - 例如 `GVIF3`、`GMSL2`、`GMSL1`、`FPD-Link III`、`FPD-Link IV`、`HSMT`
- `serial_links`
  - 串行侧媒介、链路数量、是否支持控制通道
- `video_output`
  - 例如 `MIPI CSI-2`、`D-PHY` / `C-PHY`
- `control_plane`
  - I2C / GPIO / reset / strap / lock status

这次补上的关键点是：

- 不再只靠 `application_domain` 推断使用场景
- 用 `system_path` 显式区分 camera ingress 和 display egress
- `link_families` 现在正式收纳 `HSMT`

## 4. 这次已经归一到什么程度

目前已经拉齐到统一模型的代表器件有：

- `CXD4984ER-W`
- `MAX96718A`

它们现在都具备：

- `category = Automotive Video SerDes`
- `capability_blocks.serial_video_bridge`

其中：

- `CXD4984ER-W` 还保留了更完整的 `domains.protocol` 与 `capability_blocks.mipi_phy`
- `MAX96718A` 则通过 profile 补齐了可消费的统一能力结构

另外已经纳入同一注册表、但当前处于待补档状态的器件有：

- `DS90UB934TRGZRQ1`
- `DS90UB954TRGZRQ1`
- `DS90UB960WRTDRQ1`
- `DS90UB962WRTDTQ1`
- `DS90UB9702-Q1`
- `NS6603`

这些器件当前被标记为：

- `DS90UB*`: `pending_source_reintake`
- `NS6603`: `pending_source_intake`

原因不是它们不属于同类，而是当前工作区没有它们可安全更新的正式 `extracted/export/selection` 文件。

其中 `NS6603` 当前只完成了“家族登记”：

- 已知链路家族：`HSMT`
- 未知且未 source-backed 的字段暂不猜测
- 等正式 source intake 后再激活 profile

## 5. 为什么不用只改 category

只改 `category` 不够。

因为下游真正关心的问题是：

- 这是 serializer 还是 deserializer
- 串行侧是 `GVIF3` 还是 `GMSL`
- 视频侧是不是 `CSI-2`
- 有没有 `C-PHY`
- 控制面是 I2C 还是别的
- 这颗器件是在 `camera -> domain controller` 还是 `domain controller -> display`

这些问题都不应该靠 `description` 字符串匹配。

## 6. 下游怎么用这两个关键字段

推荐下游按下面顺序判断：

1. 先看 `category == Automotive Video SerDes`
2. 再看 `capability_blocks.serial_video_bridge.system_path`
3. 最后看 `link_families`、`video_output`、`control_plane`

一个简单决策表：

- `system_path = camera_module_to_domain_controller`
  - 把它当作 sensor ingress 器件处理
  - 重点校验 serializer 配对、PoC、同轴/STP、CSI-2 接收端兼容
- `system_path = domain_controller_to_display`
  - 把它当作 display egress 器件处理
  - 重点校验显示链路时序、bridge/panel 兼容、显示控制和失锁恢复

不要只看：

- `application_domain = automotive_camera`

因为它只能说明“属于哪个大类”，不能替代系统链路位置判断。

## 7. 新同类芯片进来时怎么处理

新器件进入时，按下面流程处理。

### Step 1: 先判断是否属于这个器件族

满足任意一组强信号，就进入 `Automotive Video SerDes` 流程：

- 描述里包含 `serializer` / `deserializer` / `aggregator`
- 出现 `GMSL` / `GVIF` / `FPD-Link` / `A-PHY` / `HSMT`
- 一侧是高速串行链路，另一侧是 `CSI-2` 或视频输出
- 文档里明确提到 control channel / sideband / pass-through I2C / lock

### Step 2: 不按厂商建模，先按系统角色建模

先抽这四块：

- 串行链路侧
- 视频输出侧
- 控制面
- 复位 / 状态 / strap

并且强制补两个决策字段：

- `link_families`
- `system_path`

不要第一步就写成：

- “Sony 模型”
- “Maxim 模型”
- “TI 模型”

因为那样会把同类器件拆成无法比较的数据孤岛。

### Step 3: 在 profile 文件里登记

当前仓库采用：

- `data/normalization/automotive_video_serdes_profiles.json`

新器件进入时：

1. 增加一个 profile 条目
2. 写清 source-backed 事实
3. 只填已经确认的字段
4. 不确定的字段先留空或省略，不要猜

### Step 4: 运行归一化脚本

使用：

```bash
python3 scripts/normalize_automotive_video_serdes.py
```

脚本会把 profile 投影到：

- `data/extracted_v2/`
- `data/sch_review_export/`
- `data/selection_profile/`

如果 profile 的状态不是 `active`，或者对应文件不存在，脚本会自动跳过并打印原因，不会伪造新数据。

### Step 5: 加回归测试

至少锁住：

- `category`
- `capability_blocks.serial_video_bridge`
- `device_role`
- `link_families`
- `system_path`
- 视频输出协议

## 8. Mermaid 图看流程

```mermaid
flowchart TD
    A[新车载视频芯片] --> B{是否属于 SerDes / Bridge 族}
    B -->|是| C[补 profile]
    B -->|否| D[走普通器件流程]
    C --> C1[写 link_families]
    C1 --> C2[写 system_path]
    C2 --> E[运行 normalize_automotive_video_serdes.py]
    E --> F[data/extracted_v2]
    E --> G[data/sch_review_export]
    E --> H[data/selection_profile]
    G --> I{system_path?}
    I -->|camera_module_to_domain_controller| J[按 camera ingress 评审]
    I -->|domain_controller_to_display| K[按 display egress 评审]
```

## 9. 当前边界和自治保障

当前这套归一化是“旁路增强”，不是 exporter 主干的一部分。

这有两个好处：

- 不会把主 exporter 的复杂改动一并卷进来
- 可以先稳定同类模型，再决定是否并回主流水线

当前策略适合：

- 先把同类器件拉齐
- 再逐步把规则抽象回通用 exporter

这也意味着：

- 对 `CXD4984ER-W`、`MAX96718A` 这种已有正式数据的器件，可以直接归一
- 对 `DS90UB*` 这种当前缺正式文件的器件，先登记到注册表，等 source 回流后再激活

我现在确保自治的方法就是这 4 条：

1. 用 sidecar profile 驱动归一，不直接改动脏状态下的主 exporter
2. `active` 与 `pending_source_*` 分层，未 intake 的器件只登记，不激活
3. 归一化脚本遇到缺文件或 pending 状态会自动跳过，不会伪造导出结果
4. 用回归测试锁住 `category`、`link_families`、`system_path` 和关键 capability block

## 10. 实际消费建议

下游读取这类器件时，建议优先顺序：

1. `capability_blocks.serial_video_bridge`
2. `capability_blocks.mipi_phy`
3. `constraint_blocks.serial_video_bridge`
4. `domains.protocol`
5. `packages` / `electrical_parameters`

这能让“同类筛选”和“具体接线/评审”分层进行，而不是混在一起。

如果下游只需要一句规则：

- 先用 `category` 找到车载视频 SerDes
- 再用 `system_path` 决定它属于 camera ingress 还是 display egress
- 再用 `link_families` 和 `video_output` 做兼容性和原理图闭环
