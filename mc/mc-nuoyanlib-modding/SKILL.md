---
name: mc-nuoyanlib-modding
description: 使用模板创建基于 nuoyanlib 的网易基岩版 MC 模组，并开发功能模块。适用于网易我的世界 Python 2.7 ModSDK 项目。
---

# 基于 nuoyanlib 制作网易 MC 模组

## 新建项目

### 先确认两个名称

| 参数 | 示例 | 实际用途 |
| --- | --- | --- |
| 模组名称 | `CloudFlight` | `MOD_NAME` ，小写后形成 `cloudflight_scripts` |
| 项目根目录 | `E:\MCMod\Mod\MyProject\模组名称` | 包含 Git 仓库、源代码、开发脚本、资源的工作区 |

### 项目创建步骤

1. 完整复制 [模板](E:\MCMod\Mod\模板) 到项目根目录。
2. 使用本机 Python 3 运行 [`setup.py`](scripts/setup.py) ，并传入项目根目录，如：
  ```powershell
  py -3 setup.py "E:\MCMod\Mod\MyProject\CloudFlight"
  ```

## 参考资料

| 用途 | 默认位置 |
| --- | --- |
| 原版行为包 | `S:\MCStudioDownload\game\MinecraftPE_Netease\<version>\data\behavior_packs\vanilla` |
| 原版资源包 | `S:\MCStudioDownload\game\MinecraftPE_Netease\<version>\data\resource_packs\vanilla` |
| 原版着色器包 | `S:\MCStudioDownload\game\MinecraftPE_Netease\<version>\data\shaders` |
| 我的世界基岩版开发文档 | https://learn.microsoft.com/zh-cn/minecraft/creator/ |
| Bedrock Wiki | https://wiki.bedrock.dev/ |
| JSON UI 参考文档 | https://mcbeui.netlify.app/ |
| 网易开发文档 | https://mc.163.com/dev/mcmanual/mc-dev/ |
| 网易模组 Demo | `E:\MCMod\Demo` |

## 开发约定

- 行为包 `bp` 内代码必须使用 Python 2.7 语法，禁用 Python 3 语法；建项、清理和验证等开发脚本可以使用 Python 3 。
- 客户端和服务端分别通过 `nuoyanlib.client` / `nuoyanlib.server` 入口导入为 `nyl`，优先调用 `nyl.<func_name>`。两侧入口已包含通用接口 `nuoyanlib.common` 。
- 根据业务划分功能模块，放入 `modules/<功能>/`；创建新功能模块时，完整复制 `modules/__template/` 作为模板，然后在 `common/constant.py` 的 `ClientModule` / `ServerModule` 中注册模块。 `modules` 内各个包都有自己的客户端/服务端入口： `client.py` / `server.py` ，不同包之间应使用事件进行通信，而不是直接导入调用。
- 默认情况下，方块、实体、物品、粒子、配方、结构特征等 JSON 的命名空间统一使用 `nuoyan` ，如项目已有约定，则遵从项目约定。
- 行为包/资源包内 JSON 文件、资源文件需统一放入以项目名称命名的子目录内，如 `bp/entities/cloud_flight/` 。
- 行为包/资源包下的目录名有特定含义，不得随意命名，网易版部分命名与原版不同，具体以 Demo 为准。

**禁止** ：

- 在 Python 代码中使用 unicode 字符串。
- 使用 `namedtuple` 。

## 代码风格

- 使用 `@nyl.event` 装饰器进行事件监听，函数名与事件名一致；继承 `BaseClient` / `BaseServer` 后，编写一个与引擎事件同名的函数即可使用该事件，无需装饰器；自定义事件需注册到 `common.constant` 的 `ClientEvent` / `ServerEvent` 枚举中；使用 `args.<arg_name>` 获取事件参数。
- 自定义枚举通过 `nyl.IntEnum` / `nyl.StrEnum` 创建，枚举值命名使用大写字母和下划线，优先使用 `auto()` 生成枚举值。

## 测试

1. 读取 [mcdk-mcp-game-testing-workflow](../mcdk-mcp-game-testing-workflow/SKILL.md) 。
2. 通过 [mcdk](E:\MCMod\Tools\mcdk.exe) 启动游戏，将工作目录设为项目根目录。
3. 遵循 mcdk-mcp-game-testing-workflow 的工作流完成测试，验收结果并汇报。

禁止：

- 编写或运行任何外部测试脚本。
