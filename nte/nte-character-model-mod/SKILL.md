---
name: nte-character-model-mod
description: 使用 Blender 修改用户已打开的异环（NTE）原版角色模型，经 UE5.6 验证、烘焙后，仅打包实际修改的资源到 E:/NteMod/Backups。保持原版材质、骨骼和物理资产引用，处理 FBX 材质分区及游戏内黑材质问题。
---

# 异环角色模型修改与最小打包

入口：用户已在 Blender 打开导出的原版角色模型，并说明需要修改的部位或效果。
出口：修改后的源文件，以及 `E:/NteMod/Backups/<模组名>/<模组名>_P.pak/.utoc/.ucas`。

默认完成模型修改、必要的 UE 导入/烘焙和三件套打包；不自动安装到游戏。用户明确说“不烘焙”时停止新烘焙，复用已验证的现有输出或交付源文件，并说明已启动作业的实际状态。效果或修改边界有歧义时先问清；已授权的必要步骤不反复确认。

工具路径、AES 和 usmap 从同仓库的 [nte-modding](../nte-modding/SKILL.md) 获取。终端统一用 `pwsh`；本任务的备份、诊断副本、暂存区和日志放项目根目录 `.tmp/<任务名>/`，不改变第三方库或通用工具。UE 工程和最终 Backups 目录不是包体白名单。

## 最短路径

**原版引用基线 → Blender 局部修改 → FBX 保持独立分区 → UE 绑定原版资源并验证 → 必要烘焙一次 → 白名单暂存 → retoc 三件套及检查。**

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

### 3. 导出 FBX，恢复原版引用

- **按厘米空间导出和导入，禁止把单位换算留在根骨缩放上。** 异环（NTE）的 UE 使用厘米；源文件若为米制，需在副本中把网格坐标、全部形态键坐标及骨架休息姿态同步转换为厘米，再以厘米单位导出。只改单位显示、只放大网格，或靠 UE 的 Import Uniform Scale 补偿，均不能证明绑定正确。
- 米制源文件的一种可用做法：网格及所有形态键、骨架数据同步乘 100，场景 `scale_length=0.01`，网格与骨架对象缩放保持 1，FBX 全局缩放为 1。已有厘米源文件不得再次乘 100。须读取实际 UE 网格的参考姿态确认结果，不能仅凭导出选项推断成功。
- **根骨参考缩放必须与原版一致。** 原版为 `[1,1,1]` 时，导入结果也必须为 `[1,1,1]`；出现额外的 100 或 0.01 倍立即停止交付，修正单位与绑定后重新导入。不得只在包中把根骨数值改成 1，掩盖未同步转换的绑定矩阵。
- 使用 Blender 官方 FBX 导出器；只导出目标网格和对应骨架，保留形态键，不添加叶骨，不导出无关动画，不应用会改变形态键拓扑的修改器。
- 常用选项：`use_mesh_modifiers=False`、`add_leaf_bones=False`、`bake_anim=False`、`use_armature_deform_only=False`。轴向沿用原版可用配置；验证尺寸时统一换算到厘米，同时检查下面要求的参考姿态和动态蒙皮，不能只看包围盒。
- 防止 UE 把骨架对象容器导入为额外根骨。此环境可在导出时使用 `Armature` 容器名；只改容器，不改真实骨骼。以导入后的名称和父子关系与基线一致为准。
- 优先复用用户指定 UE 工程。取消自动创建材质/导入未修改贴图；保留原版材质槽顺序及槽名，把每个槽的 `MaterialInterface` 绑定回基线中的原版对象路径。**槽名、Blender 材质名、游戏材质资产路径是三件事。**工程占位材质只用于预览，不打包覆盖原版；确需修改材质实例时，保留原版实例类型、父材质和参数引用，不能用同名普通 Material 顶替。
- **Skeleton/PhysicsAsset 必须按原版引用的包目录放置，并用原版资产名命名。**在 UE 中使用正确的资产移动/重命名和绑定操作，不只改磁盘文件名。关闭自动生成物理资产；原版字段确认为空时保持为空，未知时继续查明，不用猜的路径顶替。
- 未修改的 Skeleton/PhysicsAsset 可以作为工程依赖放在正确位置，但不得因此纳入模组。若用户确实要求修改它们，才加入修改清单，且仍覆盖其原版包路径。

### 4. UE 验证通过再烘焙

必须确认：

1. 每个 Section 的**实际面片**都属于对应材质，不能只看槽名或槽数。FBX 若把不同材质面合进同一 Section，先修导出/导入分区，不能靠插槽或反复换槽修好。
2. 原版材质、Skeleton、PhysicsAsset 引用与基线一致；没有新增 `cloth1/cloth2/tui` 等自动生成材质资产成为运行时依赖，也没有错误生成骨架/物理资产引用。
3. 所有 UV/颜色层可用，骨骼名称/层级、形态键、模型尺寸与预期一致。范围外面片的几何及 UV 保留。
4. 按骨骼名称对照原版网格的全部真实骨骼，逐项核对父级和**局部参考变换**：厘米空间平移、旋转、缩放；四元数 `q/-q` 按等价旋转比较，派生虚拟骨另列。只核对骨骼数量、名称/父子关系、Skeleton 引用或静态尺寸不够。
5. 检查绑定矩阵与蒙皮：至少覆盖参考姿态，以及手臂、脊柱、腿等关节的非零旋转姿态；核对顶点不会塌缩、拉成长条或产生 100 倍位移。可用原版骨架驱动的 UE 动画预览，或按顶点真实权重进行 CPU 蒙皮对照；注明实际做了哪一种，CPU 检查不等于游戏实测。

已发生的故障：静态模型约 172 厘米、材质和形态目标均正常，但网格根骨参考缩放为 100，原版为 1；游戏动画驱动后出现“面条人”。因此根骨/参考姿态/动态蒙皮检查是导入验证项，不能由静态回导或 `retoc verify` 代替。

可在临时导入副本上验证，成功后更新正式网格，避免反复破坏正式资产。需要脚本化 UE 操作或读取实际 Section 面片时，按需阅读 [UE5.6 操作与故障记录](references/ue56-notes.md)。

验证通过后使用本机 NTE UE5.6 工程烘焙，保留日志；只因有新修改或失败才重烘焙。烘焙输出包含依赖是正常现象，**不意味着依赖都应打包**。

### 5. 用修改白名单暂存，不打包整个 Cooked 目录

以美术/逻辑上的实际修改建立 `changes.json`，不是按烘焙文件时间或重新导入产生的二进制差异判定。原资源被 UE 重导入/重编码，并不自动变成需要覆盖的资源。

- 只有网格修改：白名单只列网格。
- 贴图、材质实例、Skeleton、PhysicsAsset：仅在确实修改且属于本次范围时列入。
- 包内路径必须覆盖原版同一包；UE 中要先放对位置、改对资产名，不能在打包时用文件重命名掩盖错误内部名称/引用。
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
  --cooked-content "<烘焙输出工程的 Content 目录>" `
  --staging "$taskTmp/staging" `
  --report "$taskTmp/staging-report.json"
```

脚本强制显式修改白名单、原版包路径一致、完整伴随文件及精确暂存清单。它不判断修改说明的真实性，也不代替原版字段、内部名称和引用核对。

### 6. 打包并交付

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

网格发生重新导入或单位转换时，必须对最终包做 Zen→Legacy 回读，再检查实际网格的根骨缩放、原版真实骨骼参考变换和蒙皮数据，防止把错误导入版本打进成品。其他场景按需往返检查；缺少 script objects 时从共享原版母本只提供所需 `global.*` 到任务 `.tmp`，不要把环境缺失当成包体损坏。运行时问题与工具注意事项见参考文件。

交付时给出三件套目录、实际覆盖的资源、引用与分区检查结果，并区分容器校验和游戏实测。默认停在 Backups，不自动装进 `~mods`。
