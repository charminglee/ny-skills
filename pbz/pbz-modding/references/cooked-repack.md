# Cooked 资源与三件套封装

## 白名单和提取

先建立实际修改资产列表。`assets.json` 为物理包路径字符串的 JSON 数组：

```json
[
  "ProjectPBZ/Plugins/HuaShira/Content/Characters/Boss/YuCong/SkinParts/YuCong_Body.uasset"
]
```

使用脚本提取原始 Zen 数据块；这里只读取和重封装已有 Cooked 数据，不执行 Blender 到 UE 的转换：

```powershell
$taskPacker = 'E:\PbzMod\Packer'
$taskWork = 'E:\PbzMod\.tmp\任务名'
pwsh -NoProfile -File "$taskPacker\Invoke-Cue.ps1" -Action extract `
    -WorkDir $taskWork -AssetsJson $assetsJson
```

`-Action inventory -AssetRoot <前缀>` 列目录；`-Action inspect -AssetsJson <列表>` 保存包内对象 JSON。优先核对实际原版消费者和引用，再决定白名单。

提取需要保留：

- 每个选中 `FIoStoreEntry` 的 `ChunkId`、路径、所属容器和包存储条目。
- 原包的 TOC、ContainerHeader 版本。
- 对应 `PackageIds/StoreEntries` 中的 `ImportedPackages` 和 `ShaderMapHashes`。
- `TocResource.ChunkIds` 中属于选中包 ID 的全部伴随块，包括无目录路径的块，不能只按 `.ubulk` 扩展名筛选。

`FIoChunkId` 原始序列化为 12 字节。本次库内存布局：UInt64 ID 位于 0、索引位于 8、padding 位于 10、类型位于 11。助手脚本检查该布局后复制原始 12 字节，避免大小端或 ChunkIndex 丢失。类型/版本不匹配时需要重新检查，不能强行使用案例结构。

## 清单结构

```text
repack-manifest.json
  toc_version, header_version, mount_point
  packages[]
    path, chunk_id, package_id
    store_entry
      export_bundles_size, load_order, export_count, export_bundle_count
      imported_packages[], shader_map_hashes[]
  chunks[]
    id, path (允许 null), size, sha256
raw-chunks/<12字节ID的24位hex>.bin
```

修改模型时先在暂存副本中生成确实符合原生格式的 Cooked 数据，再更新这些数据块的 SHA-256。不能把 `.blend`、`.uemodel`、PNG 填进该清单当作原生资源。

## 调用固定打包器

固定部署在 `E:/PbzMod/Packer`。工具、CUE4Parse、usmap、Oodle 及预编译 CUE 助手已部署，直接使用系统 pwsh，不复制其运行时。`config.json` 记录系统 pwsh 和游戏路径，`deployment.json` 记录工具链 SHA-256。常规任务不再使用 `build_packer.ps1`，不克隆源码、编译或安装依赖。需要部署维护时才使用技能的 `scripts/deploy_packer.ps1`，输入现成已验证的程序，目标目录必须为空。

```powershell
pwsh -NoProfile -File "$taskPacker\Pack.ps1" -CheckEnvironment
pwsh -NoProfile -File "$taskPacker\Pack.ps1" `
    -Manifest "$taskWork\patched\repack-manifest.json" -Name 'zzz_ModName_P'
```

`Name` 使用英文、数字、下划线或连字符。默认交付到 `Backups/<Name>`；也可用 `-OutputDirectory` 指定新目录。已有目录不会被覆盖。清单中的 `size/sha256` 必须与 `raw-chunks` 一致，工具会先冻结输入；模型/纹理写回后须正确更新摘要。

入口自动执行封装、retoc `info/verify`，并在只含新包与游戏 `global.utoc/global.ucas` 的独立目录中挂载、提取与核对全部数据块。不会回退到原游戏的目标资产。工具缺失或哈希不匹配立即失败，不自动重建环境。程序非零退出立即终止，不能继续验证旧包。

成品目录只有三件套。输入快照、全部日志、逐块回读数据和 `result.json` 保存到脚本返回的项目 `.tmp/packer-*` 工作目录。原生数据的模型/纹理语义校验仍由任务完成；封装器回读证明数据与输入一致，不代替几何差异或纹理像素检查。

工具保留原始包数据，使用 `IoStoreWriter.write_package_chunk` 为选中包重建 StoreEntry，`write_chunk` 写附属块，`finalize` 生成新的 ContainerHeader。随后创建同名前缀空 `.pak`。

**不能复制原游戏的整个 ContainerHeader 后仅打包少量块。** 原索引中的大量缺失资源会使运行时索引不一致。常规缩减包必须重建与白名单一致的包条目。

`.pak` 小且为空是本次 IoStore 配套文件的正常形式；`.ucas` 保存数据，`.utoc` 保存索引。输出默认不加密、不压缩，避免不必要的格式变化。

## 回读与交付

1. 用可用 retoc 对候选包执行 `info`、`verify`。预期包数等于白名单，块数包括新 ContainerHeader。
2. 打包入口自动在独立目录挂载新包与必要的 global 数据，按白名单回读每个数据块；需要解析外部资产引用时另开带游戏依赖的语义检查，不能把回退到原游戏的读取当作成功。
3. 原版回包：数据块 SHA-256 一致；各模型全部 LOD 重导出的 UEFormat 一致；同一解码器得到的纹理尺寸和像素摘要一致。
4. 修改回包：对比预期差异与未修改数据，核对材质槽、骨架、物理资产和依赖，重新导出模型到 Blender 验证可见几何。索引修改另见 [index-deletion.md](index-deletion.md)。
5. 将已验证的同名前缀 `.pak/.utoc/.ucas` 复制到 `Backups/<模组名>`，逐文件比较复制前后的 SHA-256。
6. 成品目录只保留三件套，源文件快照、摘要、白名单和验证报告保存在 `.tmp`。未获安装指令时保留在 Backups；游戏内运行测试另行报告。

若用户提供的是独立 Legacy Cooked 文件组，可在确认版本和完整伴随文件后使用 retoc `to-zen --version UE5_7`；Zen/Legacy 互转时显式指定匹配版本。该版本参数不负责将旧引擎 Cooked 网格升级为新版布局。
