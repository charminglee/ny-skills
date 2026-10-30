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
$taskSkill = 'E:\Projects\ny-skills\pbz\pbz-modding'
$taskWork = 'E:\PbzMod\.tmp\任务名'
& "$taskSkill\scripts\cue_assets.ps1" -Action extract `
    -CueLib $cueLib -Paks $paks -Usmap $usmap -Oodle $oodle -AesKey $aes `
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

## 构建封装工具

```powershell
& "$taskSkill\scripts\build_packer.ps1" -WorkDir "$taskWork\build"
```

脚本在 `.tmp` 克隆固定版本的 retoc，复制本技能的小型写入程序与上游锁文件，再构建 `pbz_iostore_pack.exe`。现有共享工具和上游源码不改动。

保留上游锁定依赖：曾遇到 `lz4_flex 0.11.5` 已撤回，离线重新解析依赖失败；复用已验证提交的 `Cargo.lock` 可使用该提交的锁定依赖。不要因此随意升级第三方库或编辑其源码。

使用脚本输出的工具路径：

```powershell
& $packer "$taskWork\repack-manifest.json" "$taskWork\candidate\zzz_模组名_P.utoc"
if ($LASTEXITCODE -ne 0) { throw 'Packing failed' }
```

工具保留原始包数据，使用 `IoStoreWriter.write_package_chunk` 为选中包重建 StoreEntry，`write_chunk` 写附属块，`finalize` 生成新的 ContainerHeader。随后创建同名前缀空 `.pak`。

**不能复制原游戏的整个 ContainerHeader 后仅打包少量块。** 原索引中的大量缺失资源会使运行时索引不一致。常规缩减包必须重建与白名单一致的包条目。

`.pak` 小且为空是本次 IoStore 配套文件的正常形式；`.ucas` 保存数据，`.utoc` 保存索引。输出默认不加密、不压缩，避免不必要的格式变化。

## 回读与交付

1. 用可用 retoc 对候选包执行 `info`、`verify`。预期包数等于白名单，块数包括新 ContainerHeader。
2. CUE4Parse 挂载候选目录，并将游戏 Paks 作为依赖目录。对每个白名单包及其数据块检查实际 `IoStoreReader.Path`，确认来自候选包，不能把回退到原游戏的读取当作成功。
3. 原版回包：数据块 SHA-256 一致；各模型全部 LOD 重导出的 UEFormat 一致；同一解码器得到的纹理尺寸和像素摘要一致。
4. 修改回包：对比预期差异与未修改数据，核对材质槽、骨架、物理资产和依赖，重新导出模型到 Blender 验证可见几何。索引修改另见 [index-deletion.md](index-deletion.md)。
5. 将已验证的同名前缀 `.pak/.utoc/.ucas` 复制到 `Backups/<模组名>`，逐文件比较复制前后的 SHA-256。
6. 保存输入文件摘要、包内白名单、实际验证项、未验证项。未获安装指令时保留在 Backups；游戏内运行测试另行报告。

若用户提供的是独立 Legacy Cooked 文件组，可在确认版本和完整伴随文件后使用 retoc `to-zen --version UE5_7`；Zen/Legacy 互转时显式指定匹配版本。该版本参数不负责将旧引擎 Cooked 网格升级为新版布局。
