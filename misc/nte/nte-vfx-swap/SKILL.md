---
name: nte-vfx-swap
description: 异环 (Neverness to Everness / NTE, UE5.6) 皮肤战斗特效替换模组的分析与制作——把某套"特效皮"的战斗 VFX（普攻/技能/QTE/完美闪避/大招/变身/武器特效）套到同角色其他皮肤上，以及分析 ~mods 里同类特效模组的原理。核心手法两选一（消费者扫描定夺）：导入表重定向 mid-rename，或更稳的"内容交换"（源特效资产改名覆盖基础路径，覆盖蒙太奇/子弹Actor/GE 等全部引用方；自研 Python 包编辑器，无需 UAssetGUI）。只要用户提到"特效替换、特效皮、VFX swap、技能特效换到其他皮肤、XX皮肤的特效"、要求分析某个特效模组改了什么、或要做/重建/更新此类模组（哪怕只说"帮我把 XX 的特效换成 XX"），就用本 skill。通用解包/打包/morph/UAssetGUI 知识见同项目 nte-modding skill。
---

# NTE 皮肤战斗特效替换（VFX swap）工作流

两类任务：
- **A. 分析**：弄清某个已安装特效模组的原理（改了哪些资源、怎么生效的）。
- **B. 制作**：以某套皮肤为特效源，生成覆盖其他皮肤的模组。

两者共享步骤 1（侦察提取）。全程已验证三轮完整实现（安魂曲分析 + 黑羽制作 + 伊洛伊制作），工具脚本在 `scripts/`，格式细节与环境坑见 `references/`——**动手前先读一遍 references/format-notes.md 的"导入链"和"踩过的坑"两节**，能避开全部已知失败模式。

## 环境速查（详见 nte-modding skill）

| 项 | 值 |
| --- | --- |
| retoc | `E:\NteMod\Tools\retoc\retoc.exe`（`--aes-key` 是全局选项，放子命令**前**） |
| AES key | `0x370E80AA7DCA90A938A4D85013C5A16129AB3079902532B3325CA5B72B740FC7` |
| 游戏容器 | `...\HT\Content\{Paks,PatchPaks,TagPatchPaks}`；模组装在 `Paks\~mods` |
| 管理器备份区 | `E:\NteMod\Backups\<模组名>\`（放三件套 + mod.json） |
| 项目目录 | `E:\NteMod\Scripts\<项目名>\`（如 `blackbird_vfx`、`oneir_vfx`）：allscan/提取/脚本/out 全放这里，**不要在盘根建 nte_allscan/nte_work**（Windows Temp 会被中途清空，也别用） |

调用 retoc 时 `export MSYS_NO_PATHCONV=1` 且用 Windows 风格路径。其余 shell 坑（ugrep、heredoc、cwd 重置、硬链接）见 `references/env-gotchas.md`。

## 领域知识：皮肤/特效系统（必须先理解）

- **每套皮肤的战斗配置** = `Characters/Player/<NNN_角色>[_fashionN|_nighty|_evolve]/MeshAsset_PlayerNNN[_…]` 数据资产：引用该皮肤的网格/AnimBP/皮肤材质/武器 BP + 全部战斗 Niagara 特效（Melee/Skill/SkillA/SkillB/QTE/AirAttack/Branch/Perfectevadeattack/UltraSkill/Transform/Weapon_Loop 等）。游戏按此路径约定加载，`~mods` 同名包即覆盖。
- **技能演出** = `sequence_pack/SkillsAnimation_Live/<角色>/<角色>_skill_ultraskill[_B][_fashionN[_New]]` 等 LevelSequence（含 CineCameraActor 相机编排），内部引用一个 `*_FX` 子序列（特效编排在此）。新版皮肤常已有 per-fashion 序列变体。
- **特效本体**按皮肤分目录：`/Game/FX/Nia/Player/FX_<角色>[_Fashion_N]/`。**特效目录编号与皮肤目录编号可能错位**（实例：旧忆挽歌皮肤文件夹是 fashion2，特效却在 `FX_Lacrimosa_Fashion_3`）——以"源皮肤 MeshAsset 实际引用的目录"为准，不要按编号猜。
- **新皮肤资源在热更容器里**（`PatchPaks/`、`TagPatchPaks/`），只扫 `Paks` 会漏；且热更资源的导入链与老资源风格可能不同。`global.ucas/global.utoc` 未加密，是 retoc 解析导入名的包存储。
- 角色可能有多余文件夹（旧版/PV 用/共享贴图库/NPC 用），**没有 MeshAsset 的文件夹无法也无需打模组**。判定方法见步骤 2。

## 任务 A：分析现有特效模组

1. `retoc info / unpack` 模组三件套（模组不加密，无需 AES）看包含哪些包；对包路径与游戏约定对照，形成假设。
2. 读模组资源：把 `global.ucas+global.utoc`（从 PatchPaks 取）与模组三件套放一个临时目录，`retoc to-legacy --version UE5_6 --no-shaders` 即可转换（不需要 AES）。
3. 提取**原版**同名资源做对比：用 `scripts/make_scan_dir.py` 建全容器扫描目录，`retoc -a <KEY> to-legacy --filter <关键词>` 提取，`scripts/bnames.py` + 集合 diff 对比引用增删。
4. 报告机制：典型结论形如"模组 X 把各皮肤 MeshAsset 的战斗特效属性重定向到 Y 皮肤的特效集 + 覆盖了大招序列（剥离了源皮肤专属动画/后处理）"。引用集合"零删除纯新增"= 属性重定向的标志。

## 任务 B：制作特效替换模组

### 步骤 1 侦察提取

```bash
python <skill>/scripts/make_scan_dir.py <项目目录>   # 全容器硬链接到 <项目目录>\allscan（勿复制！34GB）
retoc --aes-key <KEY> to-legacy --version UE5_6 --no-shaders --filter <角色英文名> <项目目录>\allscan <项目目录>\<名>
retoc --aes-key <KEY> to-legacy --version UE5_6 --no-shaders --filter MeshAsset_PlayerNNN <项目目录>\allscan <项目目录>\meshall
```

`--filter` 只匹配文件名（大小写不敏感），一个关键词常有遗漏，用角色英文名、编号、中文名拼音多跑几轮。**且遗漏是无规律的**（实测 `oneir` 漏提了文件名明明含该子串的 `Oneiroi_Sequence_Fashion` 和全部 `NS_Player_Oneir_*` 特效文件）——提取完必须按"目录应该有什么"交叉核对，用更精确的文件名前缀（如 `NS_Player_Oneir`、`Oneiroi_Sequence`）补跑。

### 步骤 2 清点皮肤与判定

- 列出该角色全部 `MeshAsset*`（bb + meshall），确定特效源皮肤与目标皮肤清单。
- **玩家/NPC/旧版判定**：对全量提取的 .uasset 做引用反查（正则搜"路径片段"，按引用者目录聚合）。判定依据强度：有无 MeshAsset/AnimBP/morpher/武器 > 玩法系统动画是否引用它 > PV/过场引用（只说明是宣传资源）。有 MeshAsset 的才是皮肤系统使用的。
- 找到源皮肤引用的特效目录（`bnames.py <源MeshAsset>`），确认目标皮肤当前引用的基础特效目录。

### 步骤 3 建立映射并检查可行性

- 映射规则：目标特效对象名去掉目标前缀得"后缀"，源皮肤"前缀+后缀"即对应资产（后缀编号 1:1 对应，如 `MeleeB_003c ↔ MeleeB_Fashion_1_003c` 去前缀后相同）。
- **必须核对**：① 源皮肤没有的后缀（保留目标原版，优雅回落）；② 特殊改名项（如 `FX_X_Transform → NS_X_Fashion_1_Transform`）；③ 大招序列：源皮肤有没有专属 `_FX` 子序列、目标皮肤的 per-fashion 序列是否已存在于游戏（存在则只需覆盖换 FX 引用；不存在则要走 Lacrimosa 式"复制+剥离源皮肤专属动画/后处理再改名"的路线，复杂度高，先看有没有更简单的现成资产）。
- **消费者扫描（强制门禁，决定手法）**：对目标皮肤相关目录做引用反查，找出 MeshAsset 之外谁还直接指向基础特效目录——技能蒙太奇（`animation/skill/**`，notify 键是裸名）、Ability 的 BulletActor/UltraSkillField、伤害 GE、NPC 共用动画等。黑羽与伊洛伊都实测存在大量此类消费者：**只改 MeshAsset 导入（mid-rename）会让蒙太奇/子弹特效不换**。
  - 无外部消费者 → 用 mid-rename（步骤 4，改动最小，只发 MeshAsset+序列）。
  - 有外部消费者 → 用**内容交换**：把源特效资产内容（根对象/包名改为基础名）覆盖到基础特效路径上，所有引用方自动生效，MeshAsset/蒙太奇/主序列全原版。参照实现：`E:\NteMod\Scripts\blackbird_vfx\patch_content_swap.py`、`E:\NteMod\Scripts\oneir_vfx\patch_content_swap.py`（配套 `scan_consumers.py` 生成交换集）。序列侧同理：把源皮肤 `*_FX` 子序列内容改名覆盖到基础 `_FX` 子序列路径。
- 有意保留清单（默认）：满级光效（源皮肤常无对应资产，先 `--filter FullLevel` 确认）、模型/动画/材质/音频、目标皮肤专属武器、游泳特效、源皮肤仍引用基础版的同名后缀（如 Standby 全系）。

### 步骤 4 编辑

**A. mid-rename 路线（scripts/build_vfx_swap.py，仅限无外部消费者）**

把 CONFIG 按新角色填写（源/目标 MeshAsset、FX 目录与前缀、序列覆盖表），然后：

```bash
python build_vfx_swap.py            # dry-run: 打印每组映射与保留项，人工核对
python build_vfx_swap.py --write    # 写出 + 自动 verify（roundtrip + 无残留基版引用）
```

脚本实现的是 **mid-rename** 手法（只改导入表字符串，导入条目数不变，.uexp 零改动）。改 CONFIG 前先读 `references/format-notes.md`——特别是"**不要追加导入**"（会炸 retoc zen 往返）和"**共享 mid 按组处理**"（漏改=导入解析失败）两条。

**B. 内容交换路线（有蒙太奇/Actor/GE 等外部消费者时，首选）**

从源特效目录逐包读入，改三处后写到基础路径：`package_name`→基础完整路径、名字表里的裸名/完整路径自引用→基础名、根导出对象名→基础名；`.uexp`/`.ubulk`/`.uptnl` 原样复制。改 `package_name` 需要 `uepkg.py` 的 summary_delta 支持（黑羽完整版，已同步进 `scripts/uepkg.py`；精简版会 size mismatch 断言）。交换集=消费者后缀并集∩源特效库存，逐包校验 roundtrip + 无源前缀残留 + 根对象名正确。

### 步骤 5 打包与验证

```bash
retoc to-zen --version UE5_6 <项目目录>\out "E:\NteMod\Backups\<模组名>\<名字>_P.utoc"   # 自动生成三件套
retoc --aes-key <KEY> verify "E:\NteMod\Backups\<模组名>\<名字>_P.utoc"                   # 必须通过
```

验证的边界见 `references/format-notes.md` 最后一节：legacy 层的检查（--write 自带的 verify）是主要手段；"游戏容器+模组一起 to-legacy"提取到的永远是游戏原版（补丁链优先级），不要用它当失败证据。

### 步骤 6 交付

交付目录 `E:\NteMod\Backups\<模组名>\` 放三件套 + `mod.json`（`{"Version","Author","Optionals"}`，参照同目录现有模组）+ 一页 `README.txt`（方案/范围/副作用/互斥说明）。同时在 `E:\NteMod\Scripts\<项目名>\` 留 `README.md` 重建流水线（参照 blackbird_vfx、oneir_vfx）。提醒用户：与改同资源的其他模组互斥；游戏热更改动了这些资源后需按本流程重建。

## 文件清单

- `scripts/make_scan_dir.py` — 全容器硬链接扫描目录（防磁盘塞满 + 覆盖热更；`python make_scan_dir.py <项目目录>` → `<项目目录>\allscan`）
- `scripts/uepkg.py` — UE5.6 legacy 包精确解析/改写器（完整版：支持 package_name 摘要增量与 uexp_growth，已字节级 roundtrip 验证）
- `scripts/bnames.py` — uasset 引用字符串提取（替代 grep）
- `scripts/build_vfx_swap.py` — mid-rename 模组生成器模板（dry-run/--write/--verify，CONFIG 驱动；仅限无外部消费者）。内容交换参照 `E:\NteMod\Scripts\{blackbird_vfx,oneir_vfx}\patch_content_swap.py`
- `references/format-notes.md` — 包格式精确布局、导入链、踩坑记录、验证边界
- `references/env-gotchas.md` — 本机 shell/retoc 环境坑清单
