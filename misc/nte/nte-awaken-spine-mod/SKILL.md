---
name: nte-awaken-spine-mod
description: 异环（Neverness to Everness / NTE，UE5.6）觉醒界面动态立绘替换模组工作流。把角色觉醒界面的静态立绘替换为角色自带的 Spine 动态立绘，含控件结构、觉醒等级两套显示路径、三处等长字节补丁（克隆静态图控件为 SpineWidget、重定向 Tick/SetAnimation、角色层 idle1→idle2）、分级贴图与升级演出保留、打包与 roundtrip 校验、"1/2 有效但 3+ 无效"的排查。凡提到觉醒立绘、觉醒 Spine、动态立绘替换就用本 skill；环境与通用工具（retoc/AES/usmap/paks 母本）看 nte-modding。
---

# NTE 觉醒界面动态立绘替换

把 `BPUI_CharacterAwakenSpine_<ID>` 的静态立绘控件换成会播 Spine 动画的控件：1/2 觉醒显示动态立绘，3+ 觉醒的角色层改用同一动画（idle2），原生分级贴图与升级演出原样保留。

## 控件结构（逆向确认）

每角色一个控件，内含：`Image_CharacterNormal`（正常态）/`Image_CharacterGray`（锁定态，UMG Image）；`N_Spine1`（角色层，蓝图播 `idle1`）/`N_Spine2`（特效层，播 `idle2`，SpineWidget，属性 blob 含 Atlas/SkeletonData 对象引用）；容器 `Spine_Character`/`Spine_Effect`；升级演出 `SwitchAnim1/2/3`（MovieScene + Fx 面板/粒子）。

原生 `HTUI_CharacterAwakenSpine` 按觉醒等级切显示路径，**蓝图字节码里没有等级逻辑**：

- 1/2 觉醒显示 `Image_CharacterNormal`；
- 3+ 觉醒显示 `N_Spine1`/`N_Spine2`，并按等级注入分级 atlas 贴图 `UISpine/Awakening/<角色>/Textures/SP_xx_2~_6`（觉醒越高细节越多；控件导入表不引用这些贴图，运行时注入）。

SP 引用有两种形态：对象直接在角色目录下，或在同名子目录里；SkeletonData 名 = Atlas 名 + `_Data`。比较引用用末段对象名，别比全路径。

## 补丁（三处，全部等长字节替换）

1. **克隆静态图控件**：`Image_CharacterNormal` 的 class → `/Script/SpinePlugin/SpineWidget`，template → `/Script/SpinePlugin/Default__SpineWidget`（复用包内已有导入，不新增导入）；属性 blob 整体换成同包 `N_Spine2` 的 blob，仅把 `Widget.Slot` 的 FPI 改成该控件自己的槽位导出。
2. **驱动克隆件**：把 `N_Spine2` 的 `Tick(InDeltaTime,True)` 与 `SetAnimation(0,'idle2',True)` 两处 InstanceVariable 名字改成 `Image_CharacterNormal`。**Tick 必须一起改**：`SetAnimation` 只设置轨道，`Tick` 才 update/apply，只改前者会冻结在初始姿势。
3. **统一 3+ 动画**：`N_Spine1` 的 `StringConst('idle1')` 改成 `'idle2'`（内联 ASCII+NUL，6 字节等长，脚本内唯一）。

效果：1/2 觉醒 = 克隆件 idle2；3~6 觉醒 = 角色层 idle2 + 原生分级贴图 + SwitchAnim 演出。

边界（pak 侧无解，向用户说明）：1/2 觉醒的克隆件拿不到分级贴图；3+ 特效层因驱动让给克隆件而冻结在初始姿势（1/2 原生不显示特效层，全等级观感一致）。

## 流程

路径一律用参数/环境变量传入，脚本内不含机器专用目录。

1. **解包**：容器输入用共享母本（`paks` 目录，见 nte-modding）。
   `retoc -a <KEY> to-legacy --version UE5_6 --no-shaders --no-script-objects --filter CharacterAwakenSpine <paks> <ctrl_dir>`
   游戏热更后先重建 paks，否则硬链指向旧数据。
2. **映射**：`python scripts/awaken_tool.py map <ctrl_dir>` → 控件 ID / Awakening 目录 / SP 资产。热更新增角色必须重跑，不要复用旧表。
3. **构建**：`python scripts/awaken_tool.py build <ctrl_dir>/HT/Content/UI/Blueprints/Character/Awaken/BPUI_CharacterAwakenSpine_<ID> <out_tree> --usmap <usmap>`，打印导出号/Slot/调用偏移/SP 检查结果。输出落在 `<out_tree>/HT/Content/...`，`out_tree` 直接作为打包输入。
4. **打包**：`python scripts/awaken_tool.py pack <out_tree> <mod_dir> <Stem> --retoc <retoc>`，内含 to-zen + `info`/`list --path --size`/`verify` 三连。
5. **校验**：
   - `python scripts/awaken_tool.py verify <patched_base> <mod_dir> <Stem> <paks_dir> --retoc <retoc>`：模组三件套 + paks 的 `global.*` 硬链成 staging → to-legacy → 要求 uexp sha256 逐字节一致、导出实质字段零 diff（`.tail` 差异是 zen 往返伪影，不 gate）。
   - `python scripts/kismet_dis.py <patched_base> <ubergraph导出号>`：确认两条 `SetAnimation` 都跟 `StringConst('idle2')`（克隆件 + N_Spine1），且两个 Spine 控件都有 Tick。
6. **交付**：`Backups/<中文名>-UI-觉醒动态立绘替换/<Stem>_AwakeningLive2DReplacement_P.{utoc,ucas,pak}`，附 README 或 `verification.json`（source/patched/delivery sha256、三连、roundtrip、`runtime_tested`）。**不自动装 ~mods、不做 Release**（用户明确要求才做）。同目录若有旧版三件套，改名 `*.disabled`，否则与新版争同一资产。

## 排查：1/2 有效但 3+ 像是原版

按顺序定位，不要先怀疑补丁没写进去：

1. 用户描述分层：**1/2 有效 ⇒ 补丁已生效**，问题在等级分支换了控件；若 1/2 也无效才查导出号/克隆。
2. `retoc list --path` 查 `UISpine/Awakening/<角色>/Textures/`：有 `SP_xx_2~_6` ⇒ 高觉醒细节由原生运行时注入。
3. `kismet_dis.py` 反汇编 UberGraph：字节码只有 N_Spine1/N_Spine2 的 Tick + SetAnimation，**没有 SetVisibility/等级运算** ⇒ 分支在原生 exe。
4. 需要旁证时抽 `HTGame.exe` 字符串：`Image_CharacterNormal/Gray`、`Spine_Character/Effect`、`SwitchAnim1/2/3`、`AwakenStageLvlArray`。

结论：pak 侧改不了分支，只能改各等级显示的控件内容——这正是补丁 3 的作用。

## 角色参数

| 中文 | 控件 | SP | 英文 stem |
| --- | --- | --- | --- |
| 残虹 | 1036 | SP_CHongjx | Zankou |
| 早雾 | 1003 | SP_ZW_juexing2 | Sakiri |
| 安魂曲 | 1004 | SP_ahq_juexing3 | Lacrimosa |
| 娜娜莉 | 1010 | SP_nnl_juexing2 | Nanally |
| 白藏 | 1023 | baicang2（无 SP_ 前缀） | Baicang |
| 哈索尔 | 1025 | SP_HSR_juexing | Hathor（≠拼音） |
| 法帝娅 | 1039 | SP_FDY_juexing6 | Fadia |
| 黑羽 | 1042 | SP_HYJINGX | Blackbird |
| 浔 | 1052 | SP_xun_juexing2 | Hotori |
| 达芙蒂尔 | 1054 | SP_DFDR_juexing5 | Daffodill |
| 九原 | 1055 | SP_jy_juexing2 | Jiuyuan |
| 明音凛 | 1057 | SP_MYinJX（热更新增） | Akane |
| 卡厄斯 | 1071 | SP_KESJX2 | Chaos |
| 灵可 | 1072 | SP_lingKjx | Linko |
| 小吱 | 1073 | SP_XZ_juexing2 | Chiz |
| 伊洛伊 | 1075 | SP_YLYJX2 | Iroi |
| 真红 | 1076 | SP_ZenHJX2 | Shinku |

已交付 17 个（`Backups` 下有同名目录）。已知但未交付：薄荷 1019 `SP_BH_juexing`、哈尼娅 1020 `SP_hny_juexing4`、Yi 1008、Aidejia 1021、Adele 1033、Zero 1046/1051、Haiyue 1070。

结构差异（构建按名字查找，不硬编码）：多数控件导出号 86/316/317/55、Slot 309→20、调用偏移 73/288；法帝娅为 73/253；灵可 N_Spine1/2=324/325、Slot 317→20、331 项导出。

## 工具（本 skill 的 scripts/）

| 脚本 | 用途 |
| --- | --- |
| `awaken_tool.py` | `map` / `build` / `pack` / `verify` 四合一 |
| `kismet_dis.py` | Kismet 反汇编：`python kismet_dis.py <pkg_base> <export>` |
| `uepkg.py` | uasset/uexp 包编辑器（字节级 roundtrip 验证过） |
| `usmap_unv.py` | usmap 解析 + 无标签属性 blob 位流解码 |

`awaken_tool.py` 自己把所在目录加入 `sys.path`；环境变量 `NTE_USMAP`/`NTE_RETOC` 可替代命令行参数。

## 踩坑

- 所有补丁**必须等长**：克隆 blob 换 slot FPI、字节码名索引、idle1→idle2 都是同长度替换。
- **不要追加导入表**；也不要在脚本尾部追加新调用块——定位脚本的启发式切片会截断尾部 Return，Jump 偏移语义未证实，追加会产出损坏脚本。
- uepkg 的 summary 逐字节断言：uexp 增长会因 bulk_data_start 更新而炸，UI 资产设 `pkg.uexp_growth = 0`；uexp 重建按 serial_offset 拼接并保留尾部（尾 4 字节 magic `c1 83 2a 9e`）。
- 给名字表加名字必须同步 `pkg.names_ref_count = len(pkg.names)`，否则运行时 FName 越界。
- **不要用字面量字节搜对象引用 FPI**（各角色导入表不同），用 `Decoder` 按属性名取值。
- roundtrip 对照物是 `work/out` 里**打过补丁的** .uexp，不是游戏原版；`.tail` 重算无害。
- 新旧容器不能同时留在 ~mods：同目录旧版改名 `*.disabled`。
- 用户指定的英文 stem 与拼音/游戏目录名常不同（哈索尔=Hathor、早雾=Sakiri、浔=Hotori、小吱=Chiz、灵可=Linko、安魂曲=Lacrimosa、达芙蒂尔=Daffodill、残虹=Zankou、黑羽=Blackbird、明音凛=Akane），以用户指定为准。
- 本机 `grep` 是 ugrep（`^` 锚定会静默 0 命中），关键过滤用 python；Git Bash heredoc 会吃转义，复杂脚本写成 .py。

## 不做

- 淡入动画、圆角背景：SpineWidget 不认 RenderOpacity/ColorAndOpacity，画刷移除实测白屏，已回退不重开。
- 1/2 觉醒克隆件的分级贴图、3+ 特效层解冻：pak 侧无解，不重开。
