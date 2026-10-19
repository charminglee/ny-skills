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
4. **组织源码树**：放在项目内 `Scripts/<项目名>/work/out/HT/Content/...`，镜像游戏内路径——**必须带 `HT/` 层级**，否则 to-zen 出来的容器路径是 `../../../Content/...`，挂载后对不上游戏里的 `HT/Content/...`（实测踩过）。**不要导出到 `Projects/`**（2026-10-06 用户砍掉该环节；Projects 现在只存用户自己的 UE 工程与 Template 结构模板——Template 含 Characters/Player/<NNN_角色> 与 UI/UI、UI_Icon/AvatarImage 等常见覆盖位，是 `Content/` 开头，仅作结构参考）。只放要覆盖的文件，别放整个目录。
5. **打包**：`to-zen --version UE5_6 <项目>/work/out "E:\NteMod\Backups\<角色名-类型-名称>\<角色名-类型-名称>_P.utoc"`（输入即含 `HT/Content` 的目录本身，输出直接落 Backups，中文名），然后 `verify`。
6. **备份与交付**：交付物统一保存在 `E:\NteMod\Backups\<角色名-类型-名称>\`（中文命名，如 `黑羽-UI-动态觉醒立绘\黑羽-UI-动态觉醒立绘_P.utoc/.ucas/.pak`，容器三件套与目录同名 + `_P` 后缀；可附 README.txt 记录版本、目标游戏版本、兼容性与重建流水线）。**交付到此为止**——不导出 Projects、不做对外发布包（2026-10-06 用户已砍掉两个环节，`E:\NteMod\Release\` 里是历史产物，不再新增）。
   - **不要自动装进 `~mods`**——仅当用户明确要求安装时才复制到 `...\HT\Content\Paks\~mods\`。与覆盖同资源的其他模组互斥；游戏热更改动这些资源后需重建。
7. **验证边界**：retoc 层 verify 通过 ≠ 游戏内实测。没真进游戏就明说"游戏运行时验证未做"，别宣称已验证。

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
