---
name: nte-fmodel-iostore-repair
description: 异环（Neverness to Everness / NTE）模组在 FModel 中显示灰色、无法打开或看不到资源，或 retoc 读取模组 .utoc 报错时，诊断 IoStore 文件组、AES 与目录索引，在副本上做有证据的修复，并转换成 FModel 可读的 legacy .pak。用于归档可读性故障，不用于编辑模组资产。
---

# NTE 模组 FModel / IoStore 故障排查

## 适用范围

用户提到 NTE 模组在 FModel 中变灰、不能打开、资源列表为空，或 `retoc` 对模组 `.utoc` 报 `failed to fill whole buffer` 时使用本 skill。目标是恢复可浏览性，不改动资产内容，也不把模组安装进游戏。

核心原则：`.pak`、`.ucas`、`.utoc` 是一组不同用途的文件；小型 `.pak` 可能只是空占位索引，不能据它的大小判断整个模组损坏。先验证，再在独立副本上修复。绝不直接覆盖用户给出的原件。

## 工作流程

### 1. 清点文件组并留存原件证据

1. 用 `Get-ChildItem -LiteralPath <模组目录> -Force` 查看目录和文件名，按不含扩展名的完整文件名配对 `.pak`、`.ucas`、`.utoc`。
2. 检查配对文件确实同名。记录文件大小；对原件记录 SHA-256，完成后再核对。
3. 对 `.pak` 执行 `repak info` 和 `repak list`。如果索引显示 0 个条目，应视为“这个 `.pak` 本身没有资源条目”的证据，而不是 `.ucas/.utoc` 数据丢失的证据。
4. 不删除、重命名或修改源文件。输出目录如果已存在，改用另一个唯一目录；不要覆盖。

### 2. 确认工具、AES key 与 Oodle 环境

- 优先使用用户指定的 `retoc.exe`；没有指定时检查 `E:\NteMod\Tools\retoc\retoc.exe`。先运行 `retoc --version` 及相关子命令的 `--help`，以当前二进制实际支持的选项为准。
- Windows 下用完整路径并正确引用含空格或中文的参数。`retoc` 的全局 AES 选项必须放在子命令前，例如 `retoc -a <AES_KEY> info <file.utoc>`。
- 从 `retoc.exe` 所在目录运行，以便它能找到同目录的 `oo2core_9_win64.dll` 等压缩依赖。不要把 DLL 复制到模组源目录。
- 不要把用户给出的 AES key 写进 skill、日志或交付说明。若需命令行传递，只在本地进程中使用，输出时遮蔽 key。
- 若本机有游戏容器，可选一个已知加密的游戏 `.utoc` 作 key 对照：提供 key 时应能读取并显示 `Encrypted` 等容器信息；同一对照文件不提供 key 时应报缺少 encryption key。对照失败时先解决 key/工具问题，不要改写模组。

### 3. 先用 retoc 与 repak 做只读诊断

对每个同名 `.utoc/.ucas` 组合运行：

```powershell
retoc -a <AES_KEY> info <mod.utoc>
retoc -a <AES_KEY> list --path --size <mod.utoc>
retoc -a <AES_KEY> verify <mod.utoc>
repak info <mod.pak>
repak list <mod.pak>
```

`retoc info/list/verify` 需要能找到同目录、同 basename 的 `.ucas`。若文件组不完整或命名不一致，先报告缺失/错配；不要把缺失文件伪装成 TOC 格式错误。

区分错误类型：

- `missing encryption key`：先核实 key、加密标记和 key GUID。
- `failed to fill whole buffer`：可能是 TOC 表长度或目录索引结构损坏；只有在 AES 和文件配对已排除后，才继续检查二进制布局。这个错误本身不能证明目录计数就是根因。
- Oodle/压缩相关错误：检查 retoc 版本以及运行目录中的压缩依赖。

### 4. 结构化定位 `.utoc` 目录索引问题

当当前 retoc 版本能读取其他正常容器、AES 已验证、模组 `.ucas` 存在，但目标 `.utoc` 仍无法解析时，按该 retoc 版本支持的 `FIoStoreTocHeader` / `Toc` 布局解析文件；不可凭经验搜索一个字节并直接改写。

retoc 0.1.5 所用的常见 0x90 字节 header 中，以下字段是 little-endian：

| Header offset | 字段 |
| --- | --- |
| `0x00..0x0f` | TOC magic |
| `0x10` | TOC version (`u8`) |
| `0x14` | Header size (`u32`) |
| `0x18` | Chunk / TOC entry count (`u32`) |
| `0x1c` | Compressed block count (`u32`) |
| `0x20` | Compressed block entry size (`u32`) |
| `0x24` | Compression method name count (`u32`) |
| `0x28` | 每个 compression method 名称长度 (`u32`) |
| `0x30` | Directory index size (`u32`) |
| `0x50` | Container flags (`u8`) |
| `0x54` | Perfect-hash seed count (`u32`) |
| `0x60` | 无 perfect-hash 的 chunk count (`u32`) |

对这个 header 布局，directory index 起始位置按 TOC version 和 flags 推算，而不是固定偏移：

1. 从 header size 开始。
2. 加 `entry_count * 12`（chunk IDs）及 `entry_count * 10`（offset/length 项）。
3. TOC version 达到 `PerfectHash` 时，加 `perfect_hash_seed_count * 4`；达到 `PerfectHashWithOverflow` 时，再加 `chunks_without_perfect_hash_count * 4`。
4. 加 `compressed_block_count * compressed_block_entry_size`，再加 `method_name_count * method_name_length`。
5. 若 container flags 的 `0x04`（Signed）置位，按当前 TOC parser 消耗签名结构；不要把签名字节算进目录索引。
6. 得到 directory index 起始位置后，读取其中的 mount-point `FString`。其开头 4 字节为有符号长度；正数按该字节数读取，负数按绝对值乘 2 读取 UTF-16。第一个 directory-entry 数组计数的位置是 mount-point FString 之后的下一个 `u32`。

目录索引随后包含 directory entries、file entries 和 string table。只在下列证据都成立时，才把目录 entry count 为 0 判为可修复的单字段错误：

- 计数后仍存在可解析的表内容；
- 用候选计数完整解析后，文件边界与后续数组一致；
- 名称索引、父子目录/兄弟链接、文件链接和 file user data 均在各自合法范围内；
- 原始 TOC、`.ucas` 和其它字段无需改动即可通过 retoc 的独立校验。

若容器加密，必须由支持该版本的 retoc 使用正确 AES key 解密后解析；不要在密文中搜索字符串或猜测修复位置。若版本、header size、签名布局或表边界不符合 parser 支持范围，停止二进制修改并报告证据。

### 5. 只在副本上做最小修复

1. 创建独立输出，例如：

   ```text
   <源目录名>_FModel修复\
     IoStore_修复\
     FModel\
   ```

2. 将原文件组完整复制到 `IoStore_修复`，保留文件名和 `.pak/.ucas/.utoc` 配对。
3. 只改经上述解析确认的目录 entry count `u32`；写入长度相同的字节，保留 `.utoc` 其它所有字节不变。
4. 对修复副本重新运行 `retoc info`、`retoc list --path --size` 和 `retoc verify`。三项必须都成功，且 list 应给出合理的 NTE 包路径、chunk 数量和尺寸。
5. 对比副本中的 `.pak` 与 `.ucas` SHA-256，确认它们与源文件逐字节相同；源目录所有文件 hash 应保持不变。

不要复用某次容器的绝对偏移。一个已验证案例中，两个 `.utoc` 的目录计数分别从 `0` 修为 `6` 和 `10`，字段绝对偏移为 `1674` 和 `14520`；这些值只适用于那两个具体文件，必须对新文件重新解析并验证。

### 6. 为 FModel 生成 legacy `.pak`

FModel 不便直接浏览某些 IoStore 模组时，从修复后的文件组生成单独的 legacy `.pak`。先将修复后的模组三件套复制到临时 staging 目录；不要在用户源目录或修复副本目录内试写转换输出。

对 NTE 的角色资产，可先按本机游戏版本测试 `UE5_6`：

```powershell
retoc -a <AES_KEY> to-legacy --dry-run --no-script-objects `
  --version UE5_6 --filter 'HT/Content/Characters/Player/' `
  <staging目录> <临时输出.pak>
```

- `UE5_6` 只有在与当前 NTE build 相符时才使用；如果不是 5.6，先从本机容器/项目确认版本并查询 `retoc to-legacy --help`。
- `--filter` 用于限定转换范围；按 `retoc list` 看到的真实路径选择过滤器，不要猜路径。
- `ScriptObjects` 缺失时可用 `--no-script-objects` 进行普通资产浏览转换。若确实需要该元数据，再把同一游戏 build 的 `global.utoc` 和 `global.ucas` 硬链（os.link，勿复制）到临时 staging 目录重试——直接从共享母本 `E:\NteMod\Scripts\paks` 链即可（见 nte-modding"原版容器 staging"）；不要修改或移动游戏原容器。
- dry-run 必须退出码为 0，且报告资产失败数为 0，才进行实际转换（移除 `--dry-run`）。转换过程发生错误时要修复错误，不能以“文件已生成”当作成功。

对生成结果运行：

```powershell
repak info <输出.pak>
repak list <输出.pak>
```

检查索引中有非零条目、UE 版本/压缩信息可识别、目标角色的预期 `.uasset/.uexp/.ubulk` 路径存在。可按需从结果中读取几个文件或与源 chunk 尺寸交叉验证。`repak info/list` 成功说明 archive 结构可解析，不等于已经在 FModel UI 中实测打开。

### 7. 交付与说明

- `IoStore_修复`：保留完整的修复后 `.pak/.ucas/.utoc` 文件组，供支持 IoStore 的工具使用。
- `FModel`：放转换得到的 legacy `.pak`，明确告诉用户应加载这个文件，而非只有 347 字节、0 条目的占位 `.pak`。
- 保留源目录不动，报告修复字段、验证命令结果、转换资产数、legacy `.pak` 条目数和输出位置。
- 若没有实际启动并打开 FModel，不要声称 UI 已验证；应说明验证到 `retoc/repak` 层，并给出 FModel 中需加载的准确文件。
- 不在未获授权时将输出直接复制到游戏 `Paks/~mods`，也不覆盖现有模组。

## 已验证的故障特征

一次 NTE 模组故障中，AES key 可读取游戏主容器；两个 IoStore `.utoc` 的目录 entry count 被写成 0，但紧随其后的目录表数据仍完整存在。按真实 TOC 布局修正副本中的两个计数后，`retoc info/list/verify` 全部成功；`retoc to-legacy` 转出 15 个资产且 0 个转换失败；最终 `.pak` 被 `repak` 正确解析并列出 38 个条目。原始 `.pak/.ucas/.utoc` 的 SHA-256 未变化。FModel 图形界面没有在该次验证中直接操作，因此不能把 parser 验证表述为 UI 实测。
