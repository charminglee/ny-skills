# YuCong 已验证案例（2026-10-30）

## 资产身份

- 用户目录：`ProjectPBZ/Plugins/HuaShira/Content/Characters/Boss/YuCong`。
- 解包目录内含 216 个文件，最终导出了 15 个骨骼模型、3 套材质参数、15 张贴图。
- 输出：`E:/PbzMod/Exports/YuCong`；完整母本 `YuCong.blend`；独立部件在 `Blend/`，保留原目录区别同名资源。
- 本次起初生成过 FBX；用户随后明确了以后导出不需要 FBX，新技能遵循该指令。
- 原版衣物备份：`Blend/SkinParts/YuCong_Cloth01.blend1`，7,067 顶点、13,187 三角面；36 根网格骨骼，Blender 另含 3 个 socket 骨骼。

战斗面具的蓝图挂点为 `mask_left / mask_middle / mask_right`。过场面具可能有 781 根骨骼，不能与战斗单骨面具混为一份资源。

`BP_Monster_YuCong` 的衣物和头发组件实际引用 `CA_YuCong_Cloth01`、`CA_YuCong_Hair01`。若用户修改这些部件，应继续确认 ChaosClothAsset 的实际渲染数据；本次完成的修改目标是用户明确确认的 **YuCong_Body**。

## 材质和图集

- 身体/衣物/面具使用 `ProjectPBZ/Content/PBZContent/Characters/Boss/YuZong` 下的贴图，目录拼写为 YuZong。
- 头发引用 BaiChiLian 和 Hero_Hun 的共享贴图，另有 Engine 编辑器占位纹理引用。
- 身体色图及发光图 12288×4096，法线和 ARM 为 6144×2048；原 UV 横跨 1001–1003，Blender 预览使用 U/3。
- 材质分层的 Albedo 索引 2 引用发光图；补读原始 TextureParameterValues 后才完整取得 15 张纹理。

## 原版回包

产物 `E:/PbzMod/RepackTests/YuCong_Original`：30 个包（15 模型 + 15 纹理）、56 个原始数据块、1 个新 ContainerHeader。

已通过：retoc 容器校验、每块 SHA-256、全部 LOD UEFormat 重导出摘要、纹理解码尺寸及像素摘要、依赖链接和最终复制摘要。没有安装或游戏测试。

## 用户模型修改

用户开始口述 Cloth01；检查发现实际新保存文件为 Body，用户确认使用：

`E:/PbzMod/Exports/YuCong/Blend/SkinParts/YuCong_Body.blend`

原版 LOD0 为 55,653 顶点、97,199 面；修改后为 49,283 顶点、85,828 面。删除 11,371 面，恰好 5 个完整独立部件。没有新增/移动顶点、UV 或权重变化，骨骼和材质引用一致。

| LOD | 原面槽数 | 移除 | 保留 |
| --- | ---: | ---: | ---: |
| 0 | 97,199 | 11,371 | 85,828 |
| 1 | 77,757 | 10,455 | 67,302 |
| 2 | 62,203 | 8,915 | 53,288 |
| 3 | 37,305 | 5,440 | 31,865 |
| 4 | 8,495 | 1,388 | 7,107 |

五级都为 UInt16 索引。LOD0–3 在原始 BulkData，LOD4 在 Zen 包内。没有活跃 Nanite cluster/root page。本次只修改各数组中的删除面索引，其他字节完全保留。

保留的真实引用：

- 骨架：`/HuaShira/Characters/Boss/YuCong/YuCong_Skeleton.YuCong_Skeleton`。
- 物理：`/HuaShira/Characters/Boss/YuCong/PA_YuCong.PA_YuCong`。
- 材质：`/Game/PBZContent/Characters/Boss/YuZong/Material/MI_Boss_YuZong_Cloth.MI_Boss_YuZong_Cloth`。

交付目录：`E:/PbzMod/Backups/YuCongRemovedClothes`。

包名前缀：`zzz_YuCong_RemovedClothes_P`。只有 1 个模型包、2 个数据块和新 ContainerHeader；未写入纹理、材质或其他模型。原生 167 根骨骼、引用及依赖保留。回读 LOD0 可见几何、面朝向、UV 和权重与用户文件精确一致。

`Validation.json` 和 `SHA256SUMS.txt` 为实际结果。静态检查已通过；游戏内加载、技能、物理和切换效果尚未测试。
