---
name: nte-modding
description: 异环（Neverness to Everness / NTE，国服，虚幻引擎 5.6）通用模组制作环境与工作流——工具路径速查（retoc、UAssetGUI）、AES key、usmap 映射文件、游戏容器与 ~mods 安装位、解包/打包/verify 命令、本机 Git Bash 踩坑清单、项目目录约定（Projects/Backups/Scripts）。只要用户提到异环/NTE 模组的任何事就用本 skill：解包游戏资源、编辑 uasset、做 UI/模型/贴图/材质类模组、打包安装到 ~mods、retoc/FModel/UAssetGUI 用法或报错、问 AES key/usmap/工具在哪。皮肤战斗特效替换走 nte-vfx-swap；FModel 灰色/utoc 报错修复走 nte-fmodel-iostore-repair。
---

# NTE 通用模组环境与工作流

本 skill 是异环模组制作的环境基准和通用流程。专项任务优先用对应 skill：
- 皮肤战斗特效替换 → **nte-vfx-swap**（其环境速查与踩坑清单源自本 skill 的原始版本）
- FModel 灰色/看不到资源、retoc 读 .utoc 报错 → **nte-fmodel-iostore-repair**
- 其余（UI、模型、贴图、材质、通用解包打包）→ 本 skill

## 环境速查

| 项 | 值 |
| --- | --- |
| 游戏 | 异环 Neverness to Everness（NTE），国服 CN，版本随热更（交付说明按"CN NTE x.x"标注目标版本） |
| 引擎 | Unreal Engine **5.6**——retoc 一律 `--version UE5_6`；本地引擎 5.6.1 备用于核对：`E:\NteMod\Tools\NteUe` |
| 游戏根 | `E:\Neverness To Everness\Client\WindowsNoEditor\HT\` |
| 容器目录 | `...\HT\Content\Paks`（基础）、`PatchPaks`、`TagPatchPaks`（热更）；新皮肤等新资源只存在于热更容器里，只扫 Paks 会漏 |
| global 容器 | `global.ucas` + `global.utoc` **未加密**，是解析导入名/做对照提取的主存储 |
| 模组安装位 | `...\HT\Content\Paks\~mods\<模组名>\`，容器文件名以 `_P` 结尾（补丁优先级） |
| 加载器 | 需 mod loader：`Binaries\Win64` 下 UniversalSigBypasser.asi + cutils.dll + dsound.dll，用启动器（如 AyakaNTEBypasser）进游戏；文件位置清单见项目根 `mod_dir.txt` |
| retoc | `E:\NteMod\Tools\retoc\retoc.exe`（短选项 `-a` = `--aes-key`）。**必须从同目录取 `oo2core_9_win64.dll`**（Oodle 解压依赖，勿把 DLL 复制走，也不要在无 DLL 的目录运行）；同目录 `scriptobjects.bin` 供 to-legacy 提取 script objects 元数据 |
| AES key | `0x370E80AA7DCA90A938A4D85013C5A16129AB3079902532B3325CA5B72B740FC7`（国服）。读**游戏**容器必须带；自己打包出来的模组容器不加密、不需要 |
| usmap | `E:\NteMod\NTE_v1.3.usmap`（当前指定版本，FModel/UAssetGUI 共用）。同目录还有 NTE_v1.2、HT-5.6.1 旧版备用。热更后新资源解析失败时先怀疑 usmap 落后于游戏版本 |
| UAssetGUI | `E:\NteMod\Tools\UAssetGUI.exe`。纯 GUI：打开 .uasset 时选 UE5.6 + 指定 usmap。本机 dotnet 只有运行时没有 SDK，**无法脚本化、无法编译 C# 工具** |
| Python | `E:\NteMod\.venv\Scripts\python.exe`（3.12，已装好依赖） |
| 工作目录 | 每个模组项目一个目录 `E:\NteMod\Scripts\<项目名>\`（如 `blackbird_vfx`、`canhong_awakening`、`heiyu_awakening`），解包输出、staging、脚本、中间产物全放项目目录里。**禁止在盘根建 `E:\nte_work`/`E:\nte_allscan` 这类散目录**（用户多次明确纠正，最近一次 2026-10-05）；**别用 Windows Temp**——实测会被系统在会话中途清空 |
| 原版容器 staging | **全机唯一母本 `E:\NteMod\Scripts\paks\`**（50 个硬链：global 取 PatchPaks 热更版 + 全部 pakchunk 的 .utoc/.ucas/.pak，来自 Paks/PatchPaks/TagPatchPaks）。解包原版资源直接拿它当 to-legacy 输入目录；**项目里不要再自建容器 staging**（blackbird/oneir/shinku/zankou 的 allscan 已清理归拢）。游戏热更后跑 `E:\NteMod\Scripts\rebuild_paks.py` 重建（容器被热更替换后旧硬链指向旧数据）；roundtrip 场景把 global.* 从 paks 硬链进项目临时 staging，别再从游戏目录链 |

## retoc 命令速查（Git Bash）

```bash
export MSYS_NO_PATHCONV=1     # 之后一律 Windows 风格路径（E:\foo\bar）
R="E:\NteMod\Tools\retoc\retoc.exe"
KEY=0x370E80AA7DCA90A938A4D85013C5A16129AB3079902532B3325CA5B72B740FC7

"$R" -a "$KEY" info <x.utoc>                        # 只读：容器信息
"$R" -a "$KEY" list --path --size <x.utoc>          # 只读：列包路径
"$R" -a "$KEY" verify <x.utoc>                      # 校验（打包后必须跑且通过）
"$R" -a "$KEY" to-legacy --version UE5_6 --no-shaders --filter <关键词> <输入目录或.utoc> <输出目录>   # 解包
"$R" to-zen --version UE5_6 <loose文件根目录> <输出\名字_P.utoc>    # 打包：自动生成 .pak+.ucas+.utoc 三件套
```

要点（每条都踩过）：
- **全局选项放子命令前**：`-a`/`--aes-key` 写在 `to-legacy` 等后面会报 usage error。
- `--filter` 只匹配**文件名**（大小写不敏感），路径里的文件夹名不算；一个关键词常有遗漏，用角色英文名、资源编号、中文名拼音多跑几轮。
- 解包大范围资源务必 `--no-shaders`；需要 script objects 元数据再去掉，并确保 `scriptobjects.bin` 可用。
- `to-zen` 的输入是**镜像游戏 Content 路径的 loose 文件树**（见下"标准工作流"），输出文件名以 `_P` 结尾。
- 打包/修复后三连：`info` + `list --path --size` + `verify` 全部通过才算数；只说"文件生成了"不算成功。

## 标准工作流（通用模组）

1. **解包目标资源**：`to-legacy` + `--filter`，输入目录直接用共享母本 `E:\NteMod\Scripts\paks`（悬空包/缺名字表条目时它就是那个"全容器同目录"的 staging），输出放 `E:\NteMod\Scripts\<项目名>\` 内的子目录（如 `<项目>\work\`），不要往盘根写。对照原版资源时也用同样方式提取。
2. **读结构与引用**：
   - 提取 .uasset 的引用路径：用 `E:\NteMod\.agents\skills\nte-vfx-swap\scripts\bnames.py`（比 grep 可靠，自动滤 Wwise 噪音）。
   - 人工查看/单点修改：UAssetGUI。
3. **编辑**：
   - 单点、临时改动：UAssetGUI 手改属性。
   - 成批或重复性改动：写 Python 脚本改导入表/属性。可复用的包编辑器在 `E:\NteMod\.agents\skills\nte-vfx-swap\scripts\uepkg.py`（已字节级 roundtrip 验证）。**改导入表前先读** `E:\NteMod\.agents\skills\nte-vfx-swap\references\format-notes.md`——尤其"不要追加导入"（会炸 retoc zen 往返）。
   - 修改蓝图／UFunction 字节码，或调整影响脚本引用的名字表、导入导出映射时，必须执行下文的**完整字节码检查**；打包后的往返产物也要重查。
4. **组织源码树**：放在项目内 `Scripts/<项目名>/work/out/HT/Content/...`，镜像游戏内路径——**必须带 `HT/` 层级**，否则 to-zen 出来的容器路径是 `../../../Content/...`，挂载后对不上游戏里的 `HT/Content/...`（实测踩过）。**不要导出到 `Projects/`**（2026-10-06 用户砍掉该环节；Projects 现在只存用户自己的 UE 工程与 Template 结构模板——Template 含 Characters/Player/<NNN_角色> 与 UI/UI、UI_Icon/AvatarImage 等常见覆盖位，是 `Content/` 开头，仅作结构参考）。只放要覆盖的文件，别放整个目录。
5. **打包**：`to-zen --version UE5_6 <项目>/work/out "E:\NteMod\Backups\<角色名-类型-名称>\<角色名-类型-名称>_P.utoc"`（输入即含 `HT/Content` 的目录本身，输出直接落 Backups，中文名），然后 `verify`。
6. **备份与交付**：交付物统一保存在 `E:\NteMod\Backups\<角色名-类型-名称>\`（中文命名，如 `黑羽-UI-动态觉醒立绘\黑羽-UI-动态觉醒立绘_P.utoc/.ucas/.pak`，容器三件套与目录同名 + `_P` 后缀；可附 README.txt 记录版本、目标游戏版本、兼容性与重建流水线）。**交付到此为止**——不导出 Projects、不做对外发布包（2026-10-06 用户已砍掉两个环节，`E:\NteMod\Release\` 里是历史产物，不再新增）。
   - **不要自动装进 `~mods`**——仅当用户明确要求安装时才复制到 `...\HT\Content\Paks\~mods\`。与覆盖同资源的其他模组互斥；游戏热更改动这些资源后需重建。
7. **验证边界**：retoc 层 verify 通过 ≠ 游戏内实测。没真进游戏就明说"游戏运行时验证未做"，别宣称已验证。

## 蓝图／UFunction 完整字节码检查

适用于直接增删、改写 cooked Kismet 字节码，以及改变脚本所用名字或对象索引映射的任务。仅修改贴图等不涉及脚本的任务，不要求运行字节码检查。

**按引擎的真实序列化规则读取完整函数，不能只比对补丁字节数。** 核对当前引擎的 `Engine/Source/Runtime/CoreUObject/Public/UObject/ScriptSerialization.h`（指令序列化）和 `Engine/Source/Runtime/Core/Public/UObject/NameTypes.h`（`FScriptName` 布局）。磁盘尺寸与 VM 内存尺寸必须分别计算：

| 数据 | 本机 UE5.6 legacy 磁盘表示 | VM 内存表示 |
| --- | --- | --- |
| 脚本指令中的名字，如 `EX_NameConst` 的操作数 | `FName`，8 字节 | `FScriptName`，**12 字节**，不因构建配置改变 |
| 对象／函数引用 | `FPackageIndex`，4 字节 | `ScriptPointerType`，本机 64 位为 8 字节 |
| 字段引用 | `FFieldPath` 路径、名字和 owner，长度可变 | 字段指针，本机为 8 字节；路径内部的名字不能再按独立 `FScriptName` 累加 |

解析器应逐指令消费磁盘数据并累计 VM 长度，由解析结果生成函数的 `ScriptBytecodeSize`、磁盘脚本长度和 `Context` 等跳距。**不能拿磁盘增量替代 VM 增量，也不能手填未经解析验证的长度常数。** 插入指令后，所有受影响的 VM 跳转、执行流目标以及事件传给 Ubergraph 的入口偏移都需重新核对。

交付前必须完成：

1. **原版基线**：先让解析器通过原包所有有脚本的完整函数，确认磁盘读取长度、声明的 VM 长度和函数终止边界一致。原版未通过时先修解析器，不以猜测布局继续改包。
2. **完整读取**：修改包中所有有脚本的函数都要读到 `EX_EndOfScript`，核对磁盘脚本区恰好耗尽、累计 VM 长度等于声明值、函数后续元数据没有被吞入或留下未消费的脚本字节。空脚本按其零长度处理。
3. **引用与边界**：检查名字表索引、对象／函数导入导出索引及字段 owner 索引是否合法；按可取得的类／结构信息核对字段路径。核对参数及容器终止标记、每个 `Context` 跳距与其完整上下文表达式的 VM 长度，以及静态分支目标是否落在合法指令边界或规定的结束位置。动态目标和缺少类型信息的字段必须说明检查边界。
4. **拒绝不完整解析**：出现未知 opcode、解析停滞、越界、长度不符或错误跳距时，不能跳过后标为通过；补齐当前任务所需指令的真实读取规则，再验证。只列出几个函数名、FModel 能读取包、`retoc verify` 或容器往返通过，都不能替代此检查。
5. **回归与往返**：检查修改前后范围，保留原本应保留的调用；针对已修复的序列化错误，用旧错误样本确认检查会失败、修复样本确认通过。完成 Zen→Legacy 往返后，对成品中解回来的脚本再次运行同一完整检查，并保留报告。容器校验、字节码检查和游戏实测分别报告。

已发生的故障：残虹 E 技能模组将 `FScriptName` 错按 8 字节计算，导致新增 `Context` 跳距写成 24（应为 28），`OnRemoveEvent` 的 VM 总长写成 131（应为 135）。容器及解包往返均通过，但游戏加载该蓝图时触发 `ObjectSerializationError ... OnRemoveEvent: Bad export index 541191/10`。修复要同时纠正跳距和 VM 总长，不能因崩溃报了“索引错误”就只修改导入导出表；上述数字仅用于该故障回归，不是其他函数的固定值。

## UAssetGUI 注意

- 打开包时 UE 版本与 mapping 必须选对（UE5.6 + `NTE_v1.3.usmap`），否则导入表解析错误。
- UE5.6 新类型序列化 UAssetGUI 支持不全：打开报错或字段显示异常时，不要硬改，转用 uepkg.py 脚本路径。
- 它是 GUI 程序，别试图从命令行批处理；批量修改一律写 Python。

## 本机 Git Bash 坑清单（全部实测踩过）

完整版在 `E:\NteMod\.agents\skills\nte-vfx-swap\references\env-gotchas.md`，动手前读一遍。高频四条：
- retoc 全局选项放子命令**前**；Git Bash 下 `export MSYS_NO_PATHCONV=1` 且用 Windows 风格路径（含中文/空格的路径用 `cd` 进目录 + 相对路径最稳）。
- 本机 `grep` 实为 **ugrep**：`^` 锚定模式会静默匹配 0 条。关键过滤用 python 或 bnames.py，别信 grep 的"无结果"。
- heredoc 会吃 `\\` 转义（python 内联代码直接语法错误）；Bash 工具的 cwd 在调用间会重置——每条命令都带绝对路径。
- 给 Windows python 传路径用 `E:/NteMod/...`（盘符+正斜杠）或反斜杠，**别用** MSYS 风格 `/e/NteMod`（会被解析到当前盘根下）。

## 项目目录约定

| 目录 | 用途 |
| --- | --- |
| `Tools/retoc/` | retoc.exe + oo2core_9_win64.dll + scriptobjects.bin（三者在同一目录才完整） |
| `Tools/UAssetGUI.exe` | uasset GUI 编辑器 |
| `Tools/NteUe/` | UE 5.6.1 本地引擎（核对版本/结构用） |
| `Scripts/<项目名>/` | 每个模组/项目的脚本与中间产物（blackbird_vfx、heiyu_awakening 等）；补丁源码树在 `<项目>/work/out/HT/Content/...` |
| `Projects/` | 仅存用户自己的 UE 工程（各角色 UI 等）与 Template 结构模板；**模组流程不往这里写** |
| `Backups/<角色名-类型-名称>/` | 唯一交付终点，中文命名（目录与容器三件套同名 + `_P` 后缀） |
| `FModelOutput/` | FModel 浏览输出 |
| `素材/` | 参考图 |
| `NTE_v1.3.usmap` | 当前映射文件（FModel / UAssetGUI 用） |
| `mod_dir.txt` | 加载器/ReShade 等注入文件在游戏目录的安装位置记录 |
