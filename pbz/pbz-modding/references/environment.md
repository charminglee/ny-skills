# 本机环境与目录约定

记录日期：2026-10-30；已验证游戏构建为 `ProjectPBZ-5.7.4-301524`。更新游戏后重新核对容器、AES、映射和序列化版本。

| 用途 | 路径或值 |
| --- | --- |
| 工作区 | `E:/PbzMod` |
| 游戏 Paks | `E:/SteamLibrary/steamapps/common/PBZ/ProjectPBZ/Content/Paks` |
| usmap | `E:/SteamLibrary/steamapps/common/PBZ/ProjectPBZ-5.7.4-301524-full.usmap` |
| AES | `0x4BC8A51E5381325073F2BC7D4E3089CD557C4E9B7D453901C2C795518867E01D` |
| 已存在的模组安装位 | `E:/SteamLibrary/steamapps/common/PBZ/ProjectPBZ/Content/Paks/~mods` |
| FModel | `S:/Fmodel/FModel.exe` |
| Blender | `S:/Blender/blender.exe`，已验证 5.2.3 LTS |
| UE Format 导入器 | `C:/Users/12797/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/io_scene_ueformat` |
| 共享 retoc | `E:/NteMod/Tools/retoc/retoc.exe`，0.1.5 |
| 可用 Oodle | `E:/NteMod/Tools/retoc/oo2core_9_win64.dll` |
| 已验证的 CUE4Parse 库缓存 | `E:/NteMod/.tmp/zankou_leg/fmodel_lib` |
| 可用 Rust | `C:/Users/12797/.cargo/bin/cargo.exe` |
| 可用 UE 编辑器 | `S:/Epic Games/UE_5.6`，不是 PBZ 的 UE 5.7 环境 |

CUE4Parse 缓存路径只是本次发现的可用副本，可能被清理。脚本要求显式传入 `-CueLib`，使用前检查 `CUE4Parse.dll`、`CUE4Parse-Conversion.dll` 及其依赖。需要长期整理工具时可另建工作区 `Tools`，不能假定该目录已经安装。复用 NTE 目录中的通用 DLL 不代表使用 NTE 的 `EGame`、usmap 或资产路径。

## 目录

```text
E:/PbzMod/
  Exports/<角色或资源名>/
    <资源名>.blend                 完整模型原版母本
    Blend/<相对目录>/*.blend       用户可编辑的独立部件
    UEFormat/.../*.uemodel         原版网格，保留全部可用 LOD
    Metadata/                     原始引用、材质参数、资源清单及检查报告
    Textures/*.png
  Backups/<模组名>/                最终同名前缀三件套与说明、验证记录
  RepackTests/<测试名>/            已完成的原版回包测试记录
  .tmp/<任务名>/                  临时脚本、构建、候选包和日志
```

若用户要求 `.blend1` 原版副本，使用 `<部件名>.blend1`，不是 `.blend1.blend`。从已核对的原版文件复制，或从原版完整场景重建后正确重映射贴图；必须用 Blender 打开最终 `.blend1` 验证。不能将正在编辑的版本仅改名冒充原版。

## 本机故障记录

### 解压库未初始化

PBZ 的 FModel 日志曾反复出现 `Oodle decompression failed: not initialized`，并伴随下载 DLL 失败。可用 DLL 已在上表中；先显式初始化，再挂载容器：

```csharp
OodleHelper.Initialize(oodleDll);
using var provider = new DefaultFileProvider(
    paks, SearchOption.TopDirectoryOnly,
    new VersionContainer(EGame.GAME_UE5_7), StringComparer.OrdinalIgnoreCase);
provider.MappingsContainer = new FileUsmapTypeMappingsProvider(usmap);
provider.Initialize();
provider.SubmitKey(new FGuid(), new FAesKey(aesKey));
```

CUE4Parse 包对象接口使用不带 `.uasset` 的路径，或完整的 `包.对象` 路径。把 `xxx.uasset` 传给 `LoadPackageObject` 会被误解为对象名 `uasset`。读取原始数据时使用 `provider.Files[path]`/`SaveAsset(file)`。

### 分卷 IoStore

PBZ 主容器为 `ProjectPBZ-Windows.utoc`，数据分布在主 `.ucas` 及多个 `_sN.ucas` 中。共享 retoc 0.1.5，以及本次编译的上游 `885a8dae740cb1ce1e41ff2e74f67f9f0c118237`，直接读取该原包均出现 `ContainerHeader ... failed to fill whole buffer`。

本次检查到 retoc 的读取实现仅打开主 `.ucas` 并按绝对块偏移 seek，未切换分卷。不要将该错误直接判为 AES 错误，也不要拼接或重命名游戏原文件。使用 CUE4Parse 正确读取各分卷，再用 retoc 的写入库构建新的单卷容器。

版本值从实际容器读取，本次为：

- TOC：`ReplaceIoChunkHashWithIoHash`。
- ContainerHeader：`SoftPackageReferencesOffset`。

## 能力边界

原版 Cooked 数据重新封装无需 UE 5.7 编辑器。删面修改在满足原生索引修改条件时也已完成静态验证。任意 `.blend`、FBX 或 PNG 不能通过容器封装自动变成可运行的 UE 资源。不要仅凭机器上有 UE 5.6 就将其烘焙数据标记为 UE 5.7 可用。

本次已验证静态封装与回读；未验证游戏内运行。其他游戏构建、活跃 Nanite、增面、重绑及纹理写回的支持范围需要另行确定。
