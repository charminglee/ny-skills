---
name: mc-nuoyanlib-modding
description: 使用一般项目模板创建基于 nuoyanlib 的网易基岩版 MC 模组、安装库源码，并开发功能模块、双端通信和 NyUI。以 mc-netease-modding 作为模组制作约束；适用于网易我的世界 Python 2.7 ModSDK 项目。
---

# 基于 nuoyanlib 制作网易 MC 模组

## 先加载模组制作约束

制作或修改模组前，先读取并遵守同仓库的 [mc-netease-modding](../mc-netease-modding/SKILL.md)，将其作为模组制作约束。该技能负责架构扫描、引用链分析、端侧边界、事件监听、API 检索和改后验证；本技能补充 nuoyanlib 的具体工作方式，不重复维护这些规则。

- 同时读取目标项目的 `AGENTS.md`，保留用户已有修改；明确的用户指令优先于技能中的通用建议。
- 引用技能不在相邻目录时，在当前可用技能中查找同名技能并读取真实文件；缺失时说明缺失项，不声称已经遵守。
- 发现该技能要求的扫描或检索工具不可用时，如实说明尚未完成的检查，不将手工浏览描述为工具验证，也不跳过其业务代码门控。

## 按任务读取参考

| 当前任务 | 读取内容 |
| --- | --- |
| 从模板创建项目、设置名称和 UUID、安装 nuoyanlib | [建项与安装](references/project-setup.md)；支持 [非交互建项脚本](scripts/create_mod.py) |
| 新增功能模块、注册加载路径、事件和通信、开发 NyUI | nuoyanlib 内 `AGENTS.md` |

不必为一次任务读完所有参考。已有项目直接检查实际入口和当前内置库的实现，再进入所需开发流程。

## 参考资料

| 用途 | 默认位置 |
| --- | --- |
| 项目模板 | `E:\MCMod\Mod\模板\一般项目` |
| 官方行为包 | `S:\MCStudioDownload\game\MinecraftPE_Netease\<version>\data\behavior_packs\vanilla` |
| 官方资源包 | `S:\MCStudioDownload\game\MinecraftPE_Netease\<version>\data\resource_packs\vanilla` |
| 官方着色器包 | `S:\MCStudioDownload\game\MinecraftPE_Netease\3.10.0.420447\data\shaders` |
| 网易开发者文档 | https://mc.163.com/dev/mcmanual/mc-dev/ |

## 开发约定

- 终端使用 `pwsh`。运行时代码使用 Python 2.7；建项、清理和验证等开发脚本可以使用 Python 3。
- 客户端和服务端分别通过 `nuoyanlib.client` / `nuoyanlib.server` 入口导入为 `nyl`，优先调用 `nyl.<func_name>`。两侧入口已包含通用接口 `nuoyanlib.common` 。
- 功能放入 `modules/<功能>/`，以 `modules/__template/` 作为模板，在 `common/constant` 的 `ClientModule` 和 `ServerModule` 中注册模块。

## 完成与验证

先完成被引用技能要求的扫描、API 确认和改后检查，再验证实际产物：名称与脚本包路径一致、manifest UUID 有效且独立、模板占位符替换完毕、库与入口同级、模块路径可定位、UI 定义与装饰器对应。

静态编译使用 Python 2.7，开发脚本使用 Python 3。普通解释器不能证明 ModSDK 行为；游戏内验证应记录客户端与服务端的加载、事件、通信或 UI 结果，未运行游戏时明确说明验证范围。
