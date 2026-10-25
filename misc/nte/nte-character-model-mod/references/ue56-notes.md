# UE5.6 操作与本次故障记录

仅在需要脚本化导入、排查 Section/黑材质或复用现有烘焙输出时阅读。不要为了普通修改重复运行全部诊断。

## 本次已验证的经验

- Blender 两个 `fashion3_b` 槽引用同一材质数据块；FBX 存在重复材质对象连接。UE 导入后同一 Section 混入 29,007 个 `b` 面和 29,887 个 `a` 面。分别换材质只会使另一部分错误。用独立数据块和唯一导出标识重新导入，才恢复正确分区。
- 修复后原版 10 槽仍然成立：`tui`、`cloth2` 都绑定游戏原版 `MI_player_057_Akane_fashion3_b`，`cloth1` 绑定原版 `..._a`。独立逻辑槽不要求复制游戏材质资产。
- 临时新增 `RestoredThigh` 的顶点色着色器能在 Blender 显示，不等于 FBX/UE/游戏可用。用户最终选择回用原版 `b`，取消额外槽，补齐 UV1～UV3 和 COL0；原版 4 套 UV 不能只保留 UV0。
- 去掉腿环后仍有环状阴影，最终需要从实际几何重新计算平滑法线；对旧自定义法线求平均不算真正重新计算。
- 原版 JK 网格的 Skeleton 实际属于 `057_Akane_fashion2`。这是该网格的已知例子，不是其他皮肤的默认路径。PhysicsAsset 必须独立核对；找不到引用时不能照抄 UE 自动生成的路径。
- 后续重新导入自动创建了 `cloth1/cloth2/tui` 三个普通材质，覆盖了已恢复的原版引用。01/02 的像素 BulkData 完整且与烘焙输出哈希一致，但工程开启了独立 ShaderCodeLibrary，模组未包含新材质着色器。最终仅重定向网格的原版材质引用、排除这些新材质及未改动贴图，用户确认修复成功。

## 引用基线的证据

从游戏原版 SkeletalMesh 读取 `Materials`（含槽名、对象路径）、`Skeleton`、`PhysicsAsset`，必要时检查关联数据资产的额外运行时绑定。保留核对来源及显式空值。

UE 对象路径形如 `/Game/A/B/Asset.Asset`：包目录为 `Content/A/B`，资产名为 `Asset`。骨架和物理资产需在工程中按各自原版路径放置/命名，然后绑定到网格。原版字段为空时，不为了填一个路径而创建或打包新资产。

材质槽的原始名称、导入源标识和材质对象引用分开记录：

- `MaterialSlotName`：游戏可能按槽名或索引使用它。
- `ImportedMaterialSlotName`：用于下一次重导入匹配，应对应独立 FBX 标识。
- `MaterialInterface`：必须指向游戏原版材质对象，不能指向新生成的普通材质。

## Blender 与 FBX

优先读取正在运行的 Blender，而非重新打开文件丢掉未保存编辑。保存备份；用户当前隐藏状态也属于基线。对象模式会显示一些在绘制模式中隐藏的面，不能据此认定几何被恢复或损坏。

使用官方导出器生成副本并验证，避免为修复槽标识手写整份 FBX。`operator_properties_last()` 可能只是默认值，不能当成用户已验证过的导出配置。

本次有效导出选项：目标网格+骨架、无叶骨、无动画、无网格修改器，保留全部骨骼与形态键；导出容器名 `Armature` 避免多一层根骨。轴向和单位转换后，以 UE 中的世界尺寸/姿态与原模型一致为准。

新补面片转移所有原 UV/颜色层及权重。用对侧皮肤作参考时镜像几何、匹配正确侧骨骼权重；处理 UV 接缝，不要跨贴图图集插值。保留非目标部位的几何/UV。

## 本机 UE Python 已验证接口

- `AssetImportTask.save=False` 可先做不保存的验证导入。指定 `FbxImportUI` 的 skeletal/morph/normal/vertex-color 选项，并关闭材质、未改动贴图和物理资产自动生成。
- Interchange 导入后调用 `unreal.InterchangeManager.get_interchange_manager_scripted().wait_until_all_tasks_done(False)`，再检查 `task.get_objects()`；输入文件损坏也可能只得到空结果，应检查导入日志，不反复空跑。
- `SkeletalMaterial` 的 `imported_material_slot_name` 可通过 `get_editor_property()` 读取，不能直接赋值。保留从干净导入取得的结构，不尝试给只读字段硬赋值。
- Skeleton 按导入选项绑定并核对，不用 `set_editor_property('skeleton', ...)` 强写只读字段。对比骨骼时用组件 `get_num_bones()`、`get_bone_name(index)`、`get_parent_bone(name)`；本机没有可调用的 `get_bone_names()`。
- `SkeletalMeshEditorSubsystem.get_lod_material_slot(mesh, lod, section)` 读到 `-1` 可能表示无 LOD 覆盖，不能仅据此判定实际分区无材质。材质索引与真实面片仍需核对。
- UE 验证导出 FBX 可使用 `AssetExportTask`。本机骨骼网格导出在 `-nullrhi` 下出现断言；需要导出诊断副本时用 `-AllowCommandletRendering -RenderOffscreen`，不影响已打开的编辑器。
- 正式资产被外部命令行更新后，编辑器要执行 **Reload** 或重开工程；不要把它误当成重新导入 FBX。重新导入时仍需关闭自动创建材质，并复核原版引用。

不要硬编码本次 Section 编号/面数去处理其他角色。可将 UE 导出诊断副本的面片按全部 UV、几何指纹与源 FBX 对照，识别错误混合分区；只在有疑点时做这项检查。

## 游戏内黑材质的最短排查

1. 核对实际安装包，而不只看工程预览：资源路径、网格材质引用、贴图伴随数据、包内着色器文件。
2. 贴图 `.ubulk` 存在、尺寸合理且哈希匹配时，不要立即重画贴图或重烘焙模型。
3. 若网格引用新普通材质，且项目使用独立着色器库而包内没有相应代码，优先恢复游戏原版材质实例引用。原版着色器已在游戏中；仅打包修改网格即可。
4. 不把为 UE 预览创建的占位材质也覆盖到原版路径，否则仍可能把原版着色器替换坏。白名单只包含实际需要覆盖的资源。
5. 新自定义着色器是另一条工作流，不能声称只放一个新 `.uasset` 就能完成；用户确实要求新效果时才单独处理其编译、代码库及游戏加载依赖。

## 已有烘焙网格只需修引用时

这是正常模型导出流程的备用路径，不是每次修改模型都必须操作的环节。可复用同仓库 `nte-vfx-swap/scripts/uepkg.py` 读取已知兼容格式；使用前读取其 `references/format-notes.md`。不修改该通用库。

- 优先直接读取当前 Cooked 的完整原路径导入表。只用模组加 `global.*` 解出的外部依赖可能显示 `UnknownPackage`，不能把占位名重新打进游戏。
- 采用原导入条目原位改名，包导入完整路径、对象导入裸名及类型同步恢复；例如普通 `Material` 重定向回原版时核对实际 `MaterialInstanceConstant` 类型。
- 不追加导入，不改变原条目顺序和索引；相同旧路径要先分组再改，避免修改后漏查共享外部链。
- 只改引用时验证 `.uexp` 主体字节不变，原 `.uasset` 保留备份；名字表增长后，所有相关偏移必须正确。
- 注意原生 Cooked 可能存在正值 `data_resource_offset`。此处随 header 增长移动；本次通用库面向的 retoc Legacy 常为 `-1`，不能假定所有输入都一样。遗漏会导致 `invalid EObjectDataResourceVersion`。应在本任务包装代码补偿，不私改库。
- `to-zen` 后做 `info/list/verify` 和必要往返核对，检查导出名称、序列化大小与资源白名单。解包缺少 script objects 时只在任务临时目录提供母本 `global.*`，不自动认定容器损坏。

保留上述局部修复的证据；它不等于已完成游戏实测。该备用引用修复步骤不额外烘焙；安装仍须有用户的明确指令。常规模型修改仍按入口中的完整流程交付。
