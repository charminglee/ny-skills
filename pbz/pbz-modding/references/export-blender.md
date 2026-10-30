# 解包、模型转换与导出

## 1. 清点资源与建立基线

用 CUE4Parse 挂载实际游戏 Paks 和 usmap。先列出用户给定目录的资源，再按类型确认模型白名单；角色目录可能还有动画、控制 Rig、过场版本和布料模拟资产，不应全部当作网格转换。

`cue_assets.ps1 -Action inventory` 输出文件清单。`-Action inspect` 可将明确列出的包导出为对象 JSON，供检查蓝图挂接关系、原始引用和布料消费者。参数示例见 [cooked-repack.md](cooked-repack.md)。

记录完整物理包路径、虚拟包/对象路径、网格类型、各级 LOD、材质槽顺序与原槽名、每槽材质引用、骨骼和权重、Skeleton/PhysicsAsset 的真实完整引用。Blueprint 实际使用 `ChaosClothAsset` 时，独立 SkeletalMesh 可能只是另一份资源；追踪真正的渲染消费者。

`Metadata/Meshes.json` 使用 JSON 数组，每个网格至少保留以下字段：

```json
{
  "Source": "ProjectPBZ/Plugins/HuaShira/Content/Characters/Boss/YuCong/SkinParts/YuCong_Body.uasset",
  "Name": "YuCong_Body",
  "File": "UEFormat/HuaShira/Characters/Boss/YuCong/SkinParts/YuCong_Body.uemodel",
  "Materials": ["/Game/PBZContent/Characters/Boss/YuZong/Material/MI_Boss_YuZong_Cloth.MI_Boss_YuZong_Cloth"],
  "MaterialSlots": ["实际读取的原版槽名"],
  "Skeleton": "/HuaShira/Characters/Boss/YuCong/YuCong_Skeleton.YuCong_Skeleton",
  "PhysicsAsset": "/HuaShira/Characters/Boss/YuCong/PA_YuCong.PA_YuCong"
}
```

示例值只说明字段含义，其他网格按实际读取结果填写。长期保存的元数据优先使用相对交付目录的文件路径，精确 `Source` 作为身份依据。

## 2. 导出 UEFormat 和纹理

骨骼网格使用 `MeshExporter`，选项：

```csharp
var options = new ExporterOptions {
    LodFormat = ELodFormat.AllLods,
    MeshFormat = EMeshFormat.UEFormat,
    ExportMaterials = false,
    ExportMorphTargets = true
};
var exporter = new MeshExporter(mesh, options);
if (!exporter.TryWriteToDir(ueFormatDir, out var label, out var file))
    throw new Exception("Mesh export failed");
```

所有部件共用同一个 UEFormat 根目录，由导出器保留包路径。不要在每次导出前再拼一遍相同的原目录。骨骼和物理引用从 `USkeletalMesh` 原始字段记录，不能依靠 `.uemodel` 推断。

材质和贴图单独按完整对象路径去重，避免多个部件重复解码大图集：

1. 从网格实际材质引用 `Load<UUnrealMaterial>()`。
2. `material.GetParams(parameters, EMaterialFormat.AllLayersNoRef)`，其中 `parameters` 为 `CMaterialParams2`，取得预览参数。
3. 继续读取 `UMaterialInstanceConstant.TextureParameterValues` 的原始引用。参数名相同而 `Association/Index` 不同的值分别保留；YuCong 的分层 `Albedo [LayerParameter:2]` 实际引用发光图，单纯扁平化会漏掉。
4. 参数索引键可使用 `Name [Association:Index]`，资源以 `GetPathName()` 去重。保存原始材质对象 JSON 和整理后的参数表。
5. `TextureDecoder.UseAssetRipperTextureDecoder = true`，`TextureDecoder.Decode(texture, ETexturePlatform.DesktopMobile)`，随后 `TextureEncoder.Encode(decoded, ETextureFormat.Png, false, out extension)`。检查解码和编码结果。
6. 记录每张贴图的完整源路径、输出名、宽高、SRGB、法线标志、原始像素格式、是否虚拟纹理。不同路径出现同名贴图时按原目录或唯一标识区分，不能覆盖。

纹理依赖可能位于其他角色或共享目录。按实际材质引用补齐，不能只搜索用户指定的角色目录。不要用 AI 图像生成或重绘替代原始纹理解码。

## 3. 构建完整 Blender 场景

使用独立后台进程，不覆盖用户现场 Blender：

```powershell
& 'S:\Blender\blender.exe' --background --factory-startup --python $taskScript
```

现有 UE Format 导入接口：

```python
sys.path.append(ue_format_parent_directory)
from io_scene_ueformat.importer.logic import UEFormatImport
from io_scene_ueformat.options import UEModelOptions

root, data = UEFormatImport(
    UEModelOptions(reorient_bones=False, import_morph_targets=True)
).import_file(model_path)
```

导入器默认 `scale_factor=0.01`，即 UE 厘米转换为 Blender 米。不要重复缩放。LOD0 用于编辑，其他 LOD 继续保留在 `.uemodel` 中。`data.lods` 可用于验证和后续 LOD 映射。

导入每个部件前后记录对象集合差集；在新建网格和骨架上设置 `obj['UE_Source'] = source_path`。不同目录的同名模型使用唯一对象名，保留原始槽名、Skeleton 和 PhysicsAsset 信息到自定义属性/元数据。删除所有默认集合后必须设置有效的 `active_layer_collection`，否则导入器访问 `bpy.context.collection` 会失败。

### 顶点色恢复与数据检查

导入器曾把原始归一化颜色写入 `BYTE_COLOR.color`，引入色彩空间转换。使用导入数据直接建立 `FLOAT_COLOR/CORNER`：

```python
loop_vertices = np.empty(len(mesh.loops), dtype=np.int32)
mesh.loops.foreach_get("vertex_index", loop_vertices)
for color in data.lods[0].colors:
    if color.name in mesh.color_attributes:
        mesh.color_attributes.remove(mesh.color_attributes[color.name])
    layer = mesh.color_attributes.new(
        name=color.name, type="FLOAT_COLOR", domain="CORNER"
    )
    values = np.asarray(color.data[loop_vertices], dtype=np.float32)
    layer.data.foreach_set("color", values.ravel())
```

对比原始顶点、三角面顺序、全部 UV、归一化颜色、非零权重、骨骼名称/层级和形态键。自定义法线保留，若比较不同序列化格式的法线，按合理的角度误差判定。

### 材质与装配

- Blender 材质为基础编辑预览，游戏复杂着色器不因导出而完整重建。保留原版材质参数与引用。
- 根据 SRGB 元数据设置色图 `sRGB`、数据贴图 `Non-Color`。外部 PNG 的相对路径应按最终 `.blend` 所在目录计算。
- 横向 UDIM 图集要结合真实 UV 范围和尺寸确定映射；YuCong 为三格横向，预览节点 `U/3`，网格 UV 保持 1001–1003 原值。多行图集另行检查，不能统一套用。
- UE DirectX 法线在 Blender 预览节点反转 G，外部原图不改写。ARM 接线依据材质；YuCong 预览使用 R=AO、G=粗糙度、B=金属度。头发使用实际独立透明遮罩。
- 设置 `image.use_fake_user=True` 保存完整场景中需保留的辅助图像，否则未连入节点的图像会在重新打开时消失。独立部件只保留自己使用的图像。
- 根据原蓝图的父组件、AttachToName、相对变换装配附件；不根据部件名称猜挂点。战斗与过场版本分别放集合，互斥版本避免初始叠加显示。
- 默认选中可见网格、视图对准模型；骨架可默认隐藏并在说明中标明。完整模型是保留母本，用户修改独立部件。

## 4. 拆分独立部件与备份

完整场景建立后运行本技能的 `scripts/split_blends.py`，显式提供母本、网格清单、输出目录和 `.tmp` 报告路径。脚本逐项从母本重新加载，按 `UE_Source` 选择网格，只保留该网格、骨架及所用材质图像；外部装配约束解除，使用部件自身参考坐标。

```powershell
& 'S:\Blender\blender.exe' --background --factory-startup --python $splitScript -- `
    --master $master --models $meshesJson --asset-root $physicalAssetRoot `
    --output $blendPartsDir --report $temporaryReport
```

输出按原目录区分重复名称。重新打开每个 `.blend`，检查一个目标网格及对应骨架、数据摘要一致、可见且图像路径有效。流程不调用 FBX 导入或导出。

生成 `.blend1` 时先验证待复制的 `.blend` 与原版母本一致。复制到同目录不会改变贴图相对基准；若换目录，需要正确重映射路径。保存备份不能覆盖用户已有文件。
