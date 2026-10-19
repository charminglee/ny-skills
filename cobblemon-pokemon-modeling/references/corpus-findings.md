# 语料发现与适用范围

这些结论来自本地解包的 `Cobblemon-forge-1.5.2+1.20.1` 资产。它们描述这一版本的常见做法，不是 Minecraft、Bedrock Geometry 或未来 Cobblemon 版本的绝对规则。

本文是早期全目录文件统计，不代表逐只视觉检查。后续 120 个不同物种的模型／基础贴图／动画联合分析、Blockbench 采样及人工联系表观察见 [corpus-120-transfer.md](corpus-120-transfer.md)；两个范围的中位数不要混用。

## 目录与规模

- 宝可梦模型：`assets/cobblemon/bedrock/pokemon/models`，763 个 `.json` geometry 文件。
- 动画：`assets/cobblemon/bedrock/pokemon/animations`，676 个 `.json` 文件。
- resolver：`assets/cobblemon/bedrock/pokemon/resolvers`，758 个 `.json` 文件。
- 贴图：`assets/cobblemon/textures/pokemon`，1957 个 PNG。
- 文件夹通常采用 `NNNN_species`，文件名采用小写 snake_case；形态差异附加 `_female`、`_alolan`、`_hisuian` 等语义后缀。

## 模型统计

- 763 个 geometry 全部声明 `format_version: 1.12.0`。
- 共 31,194 个骨骼、38,490 个有效 cube；中位数为每模型 35 个骨骼、43 个 cube。
- 17,503 个 cube 至少有一个尺寸轴为 0，约占 45.5%。平面几何是主要造型语言，不是异常数据。
- 38,411 个 cube 的三个 size 分量全为整数；仅 79 个使用分数尺寸。
- 所有 cube 的 Box UV 起点为整数；未观察到逐面 UV或 poly mesh。
- 5,219 个 cube 使用 `mirror`，11,737 个 cube 使用 `inflate`。镜像和轻微膨胀很常见，但应服务于轮廓、接缝或层叠关系。
- 常见骨骼包括 `body`、`torso`、`head`、`eyes`、`eye_left/right`、`eyelid_left/right`、`jaw`、`tail`、左右四肢及其分段。根骨骼通常使用物种/形态名，而不是统一的 `root`。
- locator 很少但语义明确，例如 `target`、`ground_center`、`center`、`special_attack`、`head_top`；只在实际系统需要时添加。

## 贴图统计

- 最常见尺寸依次为 64×64、128×64、128×128、64×32、256×128、256×256；也存在少量非标准尺寸，不应把 2 的幂当作无条件硬规则。
- 每张 PNG 的非透明 RGBA 颜色中位数约为 22，90% 不超过约 37；复杂模型最高观察到 75。该数字只说明色阶克制，不能作为固定调色板上限。
- 所有 PNG 都含透明背景。1852 张只使用二值 alpha；105 张含半透明像素，主要集中在发光、透明翼、火焰和效果层。
- 观察到 826 个带 shiny 命名的文件、162 个 emissive/glow 命名文件，以及独立火焰、发光或图案帧目录。

## Resolver 统计

- 758 个 resolver 文件共定义 1768 个 variation。
- 424 个 variation 使用图层，共 441 个 layer；其中 172 个 emissive、90 个 translucent、21 个使用逐帧纹理。
- 最常见 aspect 是空基础形态与 `shiny`；还包括 female、地区形态、颜色、图案及其他物种特定 aspect。

## 如何使用这些数据

- 用统计识别风格中心，而不是机械追求平均值。
- 新资产若偏离整数 cube 尺寸、Box UV 或常见贴图规模，应记录原因并在 Blockbench 与游戏内验证。
- 不要从某个极端复杂模型推导普遍复杂度预算；以目标物种轮廓、动作和材质需求决定骨骼与 cube 数量。
