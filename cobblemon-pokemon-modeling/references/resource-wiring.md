# Cobblemon 资源接线

## 目录与命名

典型资产分布：

```text
assets/cobblemon/bedrock/pokemon/models/NNNN_species/*.geo.json
assets/cobblemon/bedrock/pokemon/animations/NNNN_species/*.animation.json
assets/cobblemon/bedrock/pokemon/resolvers/NNNN_species/*.json
assets/cobblemon/textures/pokemon/NNNN_species/*.png
```

目录用四位图鉴号加物种名；文件名和资源标识符使用小写 snake_case。具体资源包若已有约定，以项目约定为准。

## Resolver

resolver 顶层通常包含：

- `species`：例如 `cobblemon:species_name`。
- `order`：同物种多个 resolver 的匹配顺序。
- `variations`：基础形态和 aspect 覆盖。

基础 variation 显式声明 `aspects: []`、`poser`、`model`、`texture`。后续 variation 只覆盖确实变化的字段，例如 `aspects: ["shiny"]` 与另一张 texture。不要假设所有 variation 都必须重复基础字段；保留项目已有的继承/匹配语义与顺序。

常见 aspect 包括 `shiny`、`female`、`alolan`、`galarian`、`hisuian`、颜色或图案标记。不要发明未由物种数据产生的 aspect。

只加载 `aspects: []` 并不保证外观完整：花蓓蓓/花洁夫人的花朵颜色来自条件图层。遇到透明缺块，先读同物种全部 resolver 条件再判断是否需要修几何。显式 aspect 对照要标明研究选项，不冒称默认游戏状态。

## 图层

variation 的 `layers` 可表达：

- 普通覆盖贴图：`name` + `texture`。
- 发光：`emissive: true`。
- 半透明：`translucent: true`。
- 动画贴图：`texture` 对象包含有序 `frames`、`fps` 和 `loop`。

图层名应稳定且表达用途，如 `flame`、`glow`、`wings`。普通与 shiny 形态若图层颜色不同，分别指定对应图层纹理；不要让 shiny 继承错误的普通发光层。

## Poser 与动画

- resolver 的 `poser` 引用 Cobblemon 已注册的 poser。该版本资源中只有少量 JSON poser，许多 poser 可能由代码或其他注册机制提供；不要因为找不到同名 JSON 就随意新建。
- Bedrock animation 常用 `format_version: 1.8.0` 和 `animation.<species>.<state>` 命名。
- 实际前缀可能为别名或形态名，性别模型也可能共享无性别前缀；按 resolver 所选模型资源核查，不能只依赖物种字符串或内部 geometry identifier。Mr. Mime、Maushold、Oinkologne 等具体证据见 [corpus-200-extension.md](corpus-200-extension.md)。
- 动画骨骼名必须与 geometry 完全一致。常见状态包括 ground idle/walk、water idle/swim、sleep、battle idle、blink、cry、faint 及攻击动作，但只实现目标物种实际需要的状态。
- Molang 表达式、声音事件和循环长度要在 Cobblemon 运行时验证，Blockbench 预览不足以证明接线正确。

## 接线验收

1. resolver 的 species、model、poser、texture 与 layer 路径均可解析。
2. base、shiny、性别、地区和其他 aspect 的匹配顺序正确。
3. 所有同 geometry 贴图尺寸一致；图层与底图 UV 对齐。
4. animation 中不存在缺失骨骼；geometry 改名已同步更新引用。
5. Blockbench MCP 中的导出与磁盘文件一致，并在游戏内抽查形态切换、动画、发光和透明排序。
