# UE5.6 legacy 包格式与导入链（retoc 产出，实测验证）

本文档记录 retoc `to-legacy` 产出的 UE5.6 legacy 包（`LegacyFileVersion = -9`、unversioned、`PKG_FilterEditorOnly|PKG_Cooked|PKG_UsesUnversionedProperties = 0x80002200`）的精确布局。字段顺序以 trumank/retoc 源码 `retoc/src/legacy_asset.rs` 为准，已用"解析→重序列化→字节比对"roundtrip 验证。

## 摘要 (FPackageFileSummary) 字段顺序

```
u32  magic 0x9E2A83C1
i32  legacy_file_version = -9
i32  legacy_ue3 = 0
i32  file_version_ue4 = 0          (unversioned)
i32  file_version_ue5 = 0          ← 注意是 i32 不是 i16
i32  licensee = 0
u8[20] saved_hash
i32  total_header_size             ← == .uasset 文件大小
i32  custom_versions count (=0)
FStr package_name                  ← retoc 写入完整包路径（引擎原版摘要无此字段）
u32  package_flags
i32  name_count, name_offset
i32  soft_object_paths count, offset
i32  gatherable_text count, offset
i32  export_count, export_offset
i32  import_count, import_offset
i32  cell_exports count, offset    (5.6 VerseCells)
i32  cell_imports count, offset
i32  metadata_offset (=0)
i32  depends_offset
i32  soft_pkg_refs count, offset (=0,0)
i32  searchable_names_offset (=0)
i32  thumbnail_table_offset (=0)
i32  generation count(=1) + {export_count, name_count}   ← 改名字表后必须同步
FEng saved_by_engine_version       {u16,u16,u16,i32,FStr}
FEng compatible_with_engine_version
u32  compression_flags (=0)
i32  compressed_chunks count (=0)
u32  package_source
i32  additional_packages count (=0)
i32  asset_registry_data_offset
i64  bulk_data_start_offset        ← == uasset大小 + uexp大小
i32  world_tile_info_offset
i32  chunk_ids count (=0)
i32  preload_count, preload_offset
i32  names_referenced_from_export_data_count
i64  payload_toc_offset (=-1)
i32  data_resource_offset (=-1)
```

## 各表条目

- **名字表**：每条 = `FString`（i32 长度含 NUL，负数=UTF-16）+ `u16 non_case_hash` + `u16 case_hash`。名字索引即数组下标。
- **导入表**：每条 32 字节 = `class_package{i32,i32}` + `class_name{i32,i32}` + `outer i32` + `object_name{i32,i32}` + `optional i32`。（cooked 无 package_name 字段。）
- **导出表**：每条 96 字节 = `class/super/template/outer` 4×i32 + `object_name{i32,i32}` + `flags u32` + `serial_size i64` + `serial_offset i64` + 52 字节固定尾。`serial_offset` 首条 == total_header_size（导出数据从 .uexp 开始）。
- **preload 依赖**：`Vec<i32>`（FPackageIndex，4 字节一条），位于头部尾部，其后是对齐 padding。
- **FPackageIndex 编码**：导入 = `-1-表下标`（负数），导出 = `1-based`（正数），0 = 无。
- **FMinimalName number 语义**：number=N(N>0) 显示为 `名字_(N-1)`。

## 导入链（关键！）

zen 时代每个资产即一个包。对象导入是两级链：

```
[对象导入] class=/Script/Niagara:NiagaraSystem, object_name=裸名("NS_Xxx"), outer →
[包导入]   class=/Script/CoreUObject:Package,   object_name=完整资产路径("/Game/.../NS_Xxx"), outer=0
```

retoc 解析导入路径的规则（asset_conversion.rs）：outer 链反转后，`chain[0].object_name` = 包名，其余逐段以 `/` 拼接。所以上面链条解析为 `/Game/.../NS_Xxx/NS_Xxx`（包内同名对象）。

**改导入指向的正确做法（mid-rename）**：把"包导入"的 object_name 改成新资产的完整路径，把"对象导入"的裸名/类改成新值。导入表条目数、顺序、全部索引不变 → .uexp 一个字节不用动，preload 依赖天然有效。

## 踩过的坑（不要重蹈）

1. **追加导入会炸 retoc 往返**：在表尾追加新包导入并留孤儿导入，to-zen 重新生成 zen import map 后，to-legacy 的 remap 阶段会 `Option::unwrap()` panic（asset_conversion.rs ~1314）。mid-rename 完全避开此问题。
2. **共享 mid 必须分组处理**：同一资产常有 2 个对象导入共享同一个包导入。若改了 mid 之后再按路径找第二个对象导入，路径已经变了会漏改 → 该导入解析失败、属性为 null。必须先按原始路径分组、统一改写。
3. **offset 修正规则**：`import_offset` 只加名字表增量；`export_offset` 及之后的所有 offset（depends、asset_registry、preload、softobj 若指向后段）加名字+导入两个增量；`total_header_size`、`bulk_data_start`、每条导出的 `serial_offset` 加总增量；值为 0 或 -1 的字段（payload_toc/data_resource 等）不动。
4. **改名字表后**：`generations[0].name_count` 要同步更新。
5. **roundtrip 验证是唯一可信的解析器自检**：解析→重序列化→与原文件字节比对。字段顺序猜错时 roundtrip 立刻失败，不要靠肉眼对 dword。

## 验证成品容器的正确姿势

- `retoc --aes-key <KEY> verify <mod>.utoc` 必须通过。
- `retoc unpack`（不带 AES）能独立解出全部包 = 容器自洽。
- **不要**用"游戏容器+模组容器一起 to-legacy 再 diff"来验证模组：retoc 按游戏的补丁链（`pakchunkN-Windows_0_P` 等）决定优先级，模组容器不参与该链，提取结果永远是游戏原版——这是测试方法的局限，不代表模组有问题。导入表正确性应在 **legacy 层**（编辑输出目录）验证。
- retoc 单独转换模组容器时若出现大量 `/Engine/UnknownPackage` 占位，是因为解析导入包名需要游戏容器的目录索引（测试环境没给全），不是导入表坏了。区分依据：panic = 结构问题；Unknown 占位 = 环境问题。
- zen 容器的导入解析数据（per-container package store）写在容器头部里（header version `SoftPackageReferencesOffset`），游戏挂载时合并——这就是模组三件套不带 global 也能解析导入的原因。
