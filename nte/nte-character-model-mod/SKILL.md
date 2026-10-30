---
name: nte-character-model-mod
description: 使用 Blender 修改用户已打开的异环（NTE）原版角色模型，保留原版材质分区、骨骼和物理资产引用信息，交付源文件与 FBX。虚幻编辑器操作由用户手动完成；用户提供烘焙产物后，可用 retoc 仅打包实际修改的资源到 E:/NteMod/Backups 并校验容器。
---

# 异环角色模型修改与源文件交付

入口：用户已在 Blender 打开导出的原版角色模型，并说明需要修改的部位或效果。
出口：修改后的 `.blend`、FBX、修改清单及原版引用记录。用户提供烘焙产物后，可继续交付 `E:/NteMod/Backups/<模组名>/<模组名>_P.pak/.utoc/.ucas`。

虚幻编辑器内的导入、烘焙、打包和验证由用户手动完成，不通过编辑器、UE MCP、Python、命令行或 Commandlet 代行。完成模型修改和导出后先交接源文件；后续 retoc 流程以用户提供的烘焙产物为输入，不自动安装到游戏。效果或修改边界有歧义时先问清；已授权的必要步骤不反复确认。

工具路径、AES 和 usmap 从同仓库的 [nte-modding](../nte-modding/SKILL.md) 获取。终端统一用 `pwsh`；本任务的备份、诊断副本、暂存区和日志放项目根目录 `.tmp/<任务名>/`，不改变第三方库或通用工具。最终 Backups 目录不是包体白名单。

## 最短路径

**原版引用基线 → Blender 局部修改 → FBX 保持独立分区 → 交付源文件与修改清单。用户提供烘焙产物后，再做白名单暂存 → retoc 三件套及容器检查。**

### 1. 先建立原版基线

- 用 Blender MCP 读取当前文件、对象、隐藏状态、全部材质槽、UV/颜色层、形态键、骨骼层级和权重；保存当前未保存状态的 `.blend` 备份，保留用户已绘制的图像内容。
- 找到游戏原版 SkeletalMesh 的真实包路径，读取**原版资产字段和导入引用**。`.uemodel` 可辅助核对分区，不可代替 Skeleton/PhysicsAsset 引用证据。
- 把以下内容写入任务的 `baseline.json`：网格包路径；逐槽 `MaterialSlotName`、材质对象完整路径及资源类型；Section→槽位与面数；Skeleton、PhysicsAsset 的完整对象路径及核对来源。明确区分“字段为空”和“尚未查明”。
- 骨架/物理资产可能属于基础皮肤或另一套时装。禁止根据当前模型目录拼接 `_Skeleton`、`_PhysicsAsset`，也不能把 UE 自动生成的资产当成原版。

### 2. 在 Blender 只修改要求的部位

- 保留范围外几何、隐藏面、形态键、骨骼名称/父子关系、权重及全部 UV/颜色层；面片隐藏不等于删除。编辑模式与纹理绘制模式的显露操作不同，不擅自显露或删掉用户隐藏的部分。
- 去布料时先确认其下是否有皮肤；缺失处优先参考现有身体表面重建，并转移权重、**所有** UV 层和游戏原有颜色层（常见 `COL0`），不能只补 UV0。
- 默认回用原版材质实例与贴图。只改几何/UV 时，不为“Blender 看起来正常”新建游戏材质、顶点色着色器或新纹理；确需改变材质效果时再明确扩大修改范围。
- 两个槽即使都使用同一原版材质，也可能代表不同逻辑分区。为它们使用**独立 Blender 材质数据块及唯一导出标识**，可共用贴图；不要用同一数据块重复占槽。
- 皮肤环状明暗残留需区分贴图、几何与自定义法线。若几何已连续，按实际面片重新计算局部平滑法线；不要把旧自定义法线的平均值再次写回作为“重算”。

### 3. 导出 FBX

- **按厘米空间导出，禁止把单位换算留在根骨缩放上。** 异环（NTE）使用厘米；源文件若为米制，需在副本中把网格坐标、全部形态键坐标及骨架休息姿态同步转换为厘米，再以厘米单位导出。只改单位显示或只放大网格不能保证绑定正确。
- 米制源文件的一种可用做法：网格及所有形态键、骨架数据同步乘 100，场景 `scale_length=0.01`，网格与骨架对象缩放保持 1，FBX 全局缩放为 1。已有厘米源文件不得再次乘 100。记录实际采用的单位转换，不仅记录导出选项。
- **保留原版根骨参考缩放与绑定关系。** 原版为 `[1,1,1]` 时，不应因单位换算额外引入 100 或 0.01 倍缩放；不得只改根骨数值来掩盖未同步转换的绑定矩阵。
- 使用 Blender 官方 FBX 导出器；只导出目标网格和对应骨架，保留形态键，不添加叶骨，不导出无关动画，不应用会改变形态键拓扑的修改器。
- 常用选项：`use_mesh_modifiers=False`、`add_leaf_bones=False`、`bake_anim=False`、`use_armature_deform_only=False`。轴向沿用原版可用配置；在 Blender/FBX 侧核对尺寸、参考姿态与权重，尺寸统一换算到厘米。
- 导出时可使用 `Armature` 容器名；只改容器，不改真实骨骼的名称和父子关系。
- 保留原版材质槽顺序与槽名，随源文件提供每个槽对应的原版材质对象路径。**槽名、Blender 材质名、游戏材质资产路径是三件事。**骨架、物理资产的原版引用也随基线交付；未知项不得用猜测路径填补。
- 导出时顶点颜色空间必须使用线性。

### 4. 交付源文件与修改清单

- 保存修改后的 `.blend` 和 FBX，列明实际修改的网格/面片、UV、权重、形态键及单位转换；交付原版引用基线和未查明项。
- 在 Blender/FBX 范围内核对独立材质分区、全部 UV/颜色层、骨骼名称/父子关系与源文件保存情况，说明实际检查范围。不要把源文件检查表述为虚幻编辑器或游戏内验证。
- 由用户完成虚幻编辑器操作；尚未提供烘焙产物时，交付到源文件为止，不启动后续暂存和打包。

模型与 FBX 的常见问题，以及用户提供现有产物后可用的离线引用修复方式，按需阅读 [模型与 FBX 记录](references/model-fbx-notes.md)。

身体、脸部或发梢描边变淡时，先读 [描边顶点色参考](references/outline-vertex-colors.md)。已核实原版 COL0 基线后，可在 Blender 文本编辑器运行 [一键恢复脚本](scripts/fix_outline_vertex_colors.py)，选择原版与目标网格，按材质槽、位置和全部 UV 恢复可靠匹配的 RGBA；脚本保留旧网格和未匹配数据，生成诊断报告。详细输入约束、恢复方法及 LINEAR 导出要求见参考中的“一键脚本”章节。

### 5. 用户提供烘焙产物后，用修改白名单暂存

确认用户提供的产物对应本次源文件后再继续；产物版本或来源不明时先询问用户，不自行生成或替换。

以美术/逻辑上的实际修改建立 `changes.json`，不是按文件时间或重新编码产生的二进制差异判定。用户提供的目录包含依赖，并不意味着依赖都应打包。

- 只有网格修改：白名单只列网格。
- 贴图、材质实例、Skeleton、PhysicsAsset：仅在确实修改且属于本次范围时列入。
- 包内路径和内部资源名必须覆盖原版同一包；若用户提供的产物路径、名称或引用不匹配，报告差异并交回用户处理，不能在打包时用文件重命名掩盖。
- 同一修改资产的 `.uasset/.uexp` 及实际存在的 `.ubulk/.uptnl` 是完整文件组；必要伴随文件必须一起复制。不要添加与它同目录的其他资产。

白名单格式示意（路径必须替换为基线中的实值；`null` 只用于原版字段确认为空的情况）：

```json
{
  "mesh_package": "/Game/Characters/Player/NNN_Hero/player_NNN_Hero_skin",
  "original_references": {
    "skeleton": "/Game/Characters/Player/NNN_Hero/player_NNN_Hero_skin_Skeleton.player_NNN_Hero_skin_Skeleton",
    "physics_asset": null,
    "materials": []
  },
  "assets": [
    {
      "package": "/Game/Characters/Player/NNN_Hero/player_NNN_Hero_skin",
      "original_package": "/Game/Characters/Player/NNN_Hero/player_NNN_Hero_skin",
      "modified": true,
      "change": "按用户要求修改网格几何，保持原版资源引用"
    }
  ]
}
```

用随技能提供的脚本生成**全新、独立**暂存区：

```powershell
python "<技能目录>/scripts/stage_changed_assets.py" `
  --manifest "$taskTmp/changes.json" `
  --cooked-content "<用户提供的烘焙产物的 Content 目录>" `
  --staging "$taskTmp/staging" `
  --report "$taskTmp/staging-report.json"
```

脚本强制显式修改白名单、原版包路径一致、完整伴随文件及精确暂存清单。它不判断修改说明的真实性，也不代替原版字段、内部名称和引用核对。

### 6. retoc 打包与容器校验

暂存结构必须是 `staging/HT/Content/...`，在 `retoc.exe` 所在目录运行以使用其 Oodle DLL。最终名称用中文模组目录名加 `_P`，保留已有成品的可恢复副本：

```powershell
& $retoc to-zen --version UE5_6 "$taskTmp/staging" "$outputDir/${modName}_P.utoc"
if ($LASTEXITCODE -ne 0) { throw 'to-zen 失败' }
& $retoc info "$outputDir/${modName}_P.utoc"
if ($LASTEXITCODE -ne 0) { throw 'info 失败' }
& $retoc list --path --size "$outputDir/${modName}_P.utoc"
if ($LASTEXITCODE -ne 0) { throw 'list 失败' }
& $retoc verify "$outputDir/${modName}_P.utoc"
if ($LASTEXITCODE -ne 0) { throw 'verify 失败' }
```

`$outputDir` 为 `E:/NteMod/Backups/$modName`。三件套的 `list` 必须与白名单逐项一致；`ContainerHeader` 等容器元数据不是多打包的游戏资源。不能包含未修改的原版贴图、材质、骨架或物理资产，也不能包含用于修复预览的占位材质、日志、manifest、FBX 或 `.blend`。

按需用 retoc 做 Zen→Legacy 回读，核对资源白名单、内部名称和原版引用；发现用户提供的产物有问题时报告并交回用户处理。缺少 script objects 时从共享原版母本只提供所需 `global.*` 到任务 `.tmp`，不要把环境缺失当成包体损坏。

交付时给出三件套目录、实际覆盖的资源及 retoc 检查结果，注明产物由用户提供，区分源文件检查、容器校验、用户反馈与游戏实测。默认停在 Backups，不自动装进 `~mods`。
