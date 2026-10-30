---
name: pbz-modding
description: PBZ（ProjectPBZ，已验证 UE 5.7.4）的资源解包、骨骼模型与纹理导出、Blender 完整场景和各部件转换、原版 Cooked 资源回包及满足条件的删面模型写回，交付 .pak/.utoc/.ucas。用于 PBZ 角色、BOSS、模型、贴图和 IoStore 模组任务。
---

# PBZ 模组制作

## 工作目录与交付

默认工作区 `E:/PbzMod`。输入、工具、AES、usmap 与本机兼容性记录见 [environment.md](references/environment.md)；首次开始 PBZ 任务先读该文件并核对当前输入。

- 资源：`E:/PbzMod/Exports/<角色或资源名>/`。
- 模组：`E:/PbzMod/Backups/<用户指定的模组名>/`。
- 脚本运行副本、构建产物、候选包、诊断和日志：工作区 `.tmp/<任务名>/`。
- 用户给出的文件、目录和修改范围优先。终端使用 `pwsh`。

**资源导出交付：各部件 `.blend`、完整模型 `.blend`、保留全部 LOD 的 UEFormat、元数据和纹理。导出流程不生成 FBX。** 已存在的其他格式不属于自动清理范围。

推荐输出结构：

```text
Exports/<资源名>/
  <资源名>.blend
  Blend/<原版相对目录>/<部件名>.blend
  UEFormat/<导出器保留的包目录>/*.uemodel
  Metadata/
  Textures/*.png
```

## 按任务选择路径

1. **解包、导出或重新生成原版模型**：读 [export-blender.md](references/export-blender.md)。从实际包读取引用，导出网格与材质依赖，再建立完整场景及独立部件，重新打开检查。
2. **原版回包验证或已提供 Cooked 产物**：读 [cooked-repack.md](references/cooked-repack.md)。使用修改白名单构建新容器索引，输出三件套并回读。
3. **用户修改了 `.blend`**：先确认准确文件和目标包，建立几何/引用差异。原版重新封装成功不代表任意 Blender 编辑已可写回。
4. **修改仅为删面，其他数据不变**：按 [index-deletion.md](references/index-deletion.md) 检查是否可采用原生索引修改。新增/移动顶点、重拓扑、骨骼或权重变化、活跃 Nanite、复杂布料映射等不沿用该方法的成功结论；说明具体缺口，再选择实际可验证的路径。

本次 YuCong 的资产、数据量和验证边界见 [yucong-record.md](references/yucong-record.md)。这些是案例值，不作为其他模型的固定参数。

## 需要保持的约束

- 用户口述部件名、磁盘文件名和实际 `UE_Source` 不一致时先核对；修改时间只能帮助定位，不能证明修改内容。保存原版母本和修改文件摘要，防止打包到错误版本。
- 读取实际 SkeletalMesh 的材质槽、Skeleton、PhysicsAsset、依赖和各级 LOD。引用为空与尚未查明要区分，不能按目录或命名补猜。
- 网格修改只打包对应模型与其必要数据块。材质、纹理、Skeleton、PhysicsAsset 仅在本次实际修改时进入白名单。完整模型预览使用的资源集合不等于模组白名单。
- 同名部件按原资源相对目录保存，区分战斗、过场和 `seqs` 版本。完整模型与独立文件均保留权重、骨骼、全部 UV、法线、材质分区和顶点色。
- 使用后台 Blender 转换；使用现场 Blender 时先读取状态，避免覆盖用户未保存的场景。保存的编辑模式数据在后台检查时先切换对象模式。
- `FLOAT_COLOR` 保存原始归一化顶点色，不能把导入器的 `BYTE_COLOR` 色彩转换结果直接当作无损基线。
- 未明确要求安装时，成品保存在 Backups。静态容器检查、Blender 回读和游戏内验证分别报告。

## 最终检查

- 导出：完整场景可打开，各部件只含目标网格及其骨架；外部贴图相对路径有效；重复材质槽与源引用可追溯；没有生成 FBX。
- 原版回包：新包数据块、完整 LOD 模型和贴图像素与原版匹配。
- 修改回包：包内只有白名单资源；回读确实来自新容器；可见几何与修改文件一致；未修改的 UV、颜色、权重和各类引用保留；其余 LOD 按实际改动核对。
- 成品复制后核对 SHA-256，提供三件套、输入摘要和验证结果。未进行游戏运行测试时明确说明。

## 辅助工具

- [cue_assets.ps1](scripts/cue_assets.ps1)：用明确提供的 CUE4Parse 库执行目录清单、对象检查和原始 Zen 数据块提取；配置和运行结果写入工作区 `.tmp`。
- [build_packer.ps1](scripts/build_packer.ps1)：在 `.tmp` 构建固定上游版本的 IoStore 封装工具，不改动共享工具或上游源码。
- [split_blends.py](scripts/split_blends.py)：从原版完整场景生成独立部件，并逐个回读核对模型数据和贴图路径；需先按导出流程在网格上记录 `UE_Source`。
