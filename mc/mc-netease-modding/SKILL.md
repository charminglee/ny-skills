---
name: mc-netease-modding
description: 网易基岩版 MOD Python 开发强制工作流。未知项目必须先 scan_py2_mod_architecture 建立认知；改动已有模块必须先 scan_py2_import_chain 分析引用链；禁止单文件堆积；禁止跨端侧 import；事件监听优先注册表分发避免重复注册；游戏业务非必要不 try 且不吞异常；关键决策点必须确认用户意图。
---

# MOD 开发工作流约束

本规范是强制性工作流，适用于网易基岩版 MC MOD 的 Python 业务开发。以下所有"必须"均为硬性门控，未通过则不得进入下一阶段。

## 代码编写约束

### 1.1 客户端/服务端 import 边界约束

MOD 业务分为服务端（Server）和客户端（Client）两侧，Python 的 `import` 具有初始化语义，不只是取符号。

**硬性规则**：

- 不得在客户端模块中 import 服务端业务模块，反之亦然
- 不得在 `__init__.py` 中混合导入客户端和服务端业务模块——`__init__.py` 包内导入必须严格确认目标模块属于哪一侧
- 不得在错误线程上初始化对应侧的对象（PyModSdk 基于多线程 GIL 轮换，客户端与服务端对象不是独立副本）

**例外——跳板封装库**：

以下导入本身是合法的，因为它们只在实际调用内部接口时才进入对应侧初始化逻辑：

- `import mod.server.extraServerApi as serverApi`
- `import mod.client.extraClientApi as clientApi`

但前提是：不得在错误线程或错误侧继续调用其内部能力。仅导入无影响，调用才触发初始化。


### 1.3 文件职责约束

**硬性规则**：

- 新增功能时，如果与目标文件的现有职责不同，必须新建文件
- 新增子系统必须建立独立目录

**决策规则**：

- 当你准备向一个文件添加代码时，先判断：这段代码的职责是否与该文件现有内容一致？
  - 一致 → 写入
  - 不一致 → 新建文件，放到职责匹配的位置
- 当你发现一个文件已经承担了多个不相关职责 → 在改动方案中标注"建议拆分"，但当前任务只做必要改动，不擅自大规模重构

**禁止**：
- 禁止在单个文件中堆积超过两个不相关的功能模块
- 禁止为了"方便"把所有新增逻辑都追加到一个已有文件末尾

### 1.4 代码结构约束

**硬性规则**：

- 使用早返回（guard clause）模式避免嵌套地狱：当条件不满足时尽早 `return`，而非层层嵌套 `if`
- 函数嵌套层级不应超过 3 层，超过时必须通过早返回或拆分子函数来降低复杂度

**决策规则**：

- 当你准备写 `if xxx:` 且内部有大段逻辑时，考虑是否可以反转为 `if not xxx: return`
- 多个前置条件检查应逐个早返回，而非嵌套

反例：

```python
# 伪代码演示
def OnPlayerAttack(args):
    playerId = args.get("playerId")
    if playerId:
        targetId = args.get("targetId")
        if targetId:
            comp = CreateComponent(playerId, "Minecraft", "attack")
            if comp:
                damage = comp.GetAttr()
                if damage is not None:
                    ApplyDamage(targetId, damage)
```

推荐：

```python
def OnPlayerAttack(args):
    playerId = args.get("playerId")
    if not playerId:
        return
    targetId = args.get("targetId")
    if not targetId:
        return
    comp = CreateComponent(playerId, "Minecraft", "attack")
    if not comp:
        return
    damage = comp.GetAttr()
    if damage is None:
        return
    ApplyDamage(targetId, damage)
```

### 1.5 事件监听约束

- 事件监听接口统一使用 `@nyl.event` 装饰器。
- 同对于同一个事件，在同一个模块内应只注册一次监听。
- 当你准备为某个事件写监听时，先检查：项目中是否已有该事件的监听？ → 有 → 不要再注册一次，应该把新的处理逻辑挂到已有的事件回调函数上。

### 1.6 异常处理约束

**硬性规则**：

- 游戏业务代码（tick、事件回调、循环、组件调用）中，非必要不得使用 `try/except`
- 优先使用显式判断（`if x`、`x in dict`）代替异常捕获
- 如确需使用 `try`，必须同时满足以下全部条件：
  1. 捕获明确的异常类型（禁止裸 `except:` 和 `except Exception: pass`）
  2. 异常处理块中必须保留错误信息（`traceback.print_exc()` 或 logging）
  3. 该异常确实是不可预期的外部错误（文件IO、网络、第三方库）

**决策规则**：

- 当你准备写 `try` 时，先问自己：
  - 这个错误能否通过前置判断避免？ → 能 → 用 `if` 判断，不用 `try`
  - 这是热路径（tick/循环/高频事件）吗？ → 是 → 除非绝对必要，不用 `try`
  - 如果必须用 `try`：是否指定了明确异常类型？是否保留了错误日志？ → 两者都满足才可以写

**禁止**：
- 禁止 `except: pass` 或 `except Exception: pass`（吞异常）
- 禁止用 `try/except KeyError` 代替 `dict.get()`
- 禁止用 `try/except AttributeError` 代替 `hasattr()` 或 `is not None` 检查
- 禁止用 `try/except StopIteration` 代替 `next(it, default)` 或 `for` 循环

### 1.7 资料检索约束

**硬性规则**：

- 编写涉及 ModAPI 接口、事件、枚举、JSON 字段、资源路径的代码前，必须先通过 MCP 工具检索确认
- 不得凭记忆或猜测编写 API 调用、事件名、枚举值

**搜索技巧**：

- 网易侧工具（`search_api`、`search_event`、`search_enum`、`search_all`、`search_netease_guide`、`search_qumod`）支持中文模糊匹配
- 单次搜索关键词应精简聚焦，建议一次只查一个概念；塞入过多内容会降低准确性
- 搜索结果不理想时，换关键词或拆分为多次搜索
- 国际版通用内容用 `search_wiki`、`search_bedrock_dev`（英文关键词）
- 原版资源文件用 `search_game_assets`

**工具对照表**：

| 查什么 | 用什么工具 |
|--------|-----------|
| ModAPI 接口 | `search_api` |
| ModAPI 事件 | `search_event` |
| ModAPI 枚举 | `search_enum` |
| 以上混合搜索 | `search_all` |
| 网易独占教程 | `search_netease_guide` |
| QuModLibs 框架 | `search_qumod` |
| Bedrock Wiki | `search_wiki` |
| JSON 组件格式 | `search_bedrock_dev` |
| 原版资源文件 | `search_game_assets` |
| 网易版差异 | `get_netease_diff` |
| 网易 JSON UI 组件库 | `get_netease_jsonui` |

**禁止**：
- 禁止在未检索的情况下编写包含 API 名、事件名、枚举值的代码
- 禁止在资料不足时硬猜字段名或参数格式，应明确告知用户"资料中未找到，需要确认"

## 改动后验证

**触发条件**：完成任何代码编写或修改后。

**硬性规则**：改完代码后，必须执行以下验证步骤，不得跳过。

1. **import 链完整性**：对修改过的文件重新调用 `scan_py2_import_chain`，确认：
   - 没有引入新的跨端侧 import
   - 没有产生循环依赖
   - 所有引用方的 import 路径仍然有效（尤其是重命名/移动/拆分后）
2. **端侧边界检查**：确认新增/修改的文件没有混入错误端侧的导入或初始化
3. **事件监听配对**：如果新增了事件监听注册，确认有对应的注销逻辑
4. **代码风格一致性**：确认新增代码的命名风格、目录位置与项目已有风格一致

**注意**：如果验证发现问题，必须修复后再提交，不得带着已知问题交付。

## 何时停下来问用户

以下场景中，AI 必须停下来向用户确认，不得自行决定：

- **架构风格不明确**：项目中存在多种组织风格，无法判断应该遵循哪一种
- **重构范围超出任务**：当前任务的最佳实现方式需要大范围重构已有代码
- **新增子系统的放置位置**：项目结构中没有明确的位置适合放置新功能
- **事件监听架构决策**：需要建立新的注册表分发机制，或需要改变已有的事件管理方式
- **端侧归属不确定**：某个模块或功能无法明确判断属于客户端还是服务端
- **资料库中未找到所需信息**：API、事件、字段等在资料库中查不到，需要用户确认
- **破坏性改动**：改动可能影响已有功能的行为（如修改公共接口的签名、改变事件参数结构）

**原则**：宁可多问一次，不可做错一步。错误的架构决策比多一轮对话的成本高得多。

## 工作流总览

```
收到任务
  │
  ├─ 1. 项目是否已知？
  │   ├─ 否 → 【阶段零】scan_py2_mod_architecture → 建立认知 → 识别架构风格
  │   └─ 是 → 继续
  │
  ├─ 2. 是否涉及已有模块改动？
  │   ├─ 是 → 【阶段一】scan_py2_import_chain → 分析引用链 → 制定方案
  │   └─ 否（纯新增）→ 确认新文件放置位置是否符合架构风格
  │
  ├─ 3. 是否涉及 ModAPI / 事件 / 资源？
  │   ├─ 是 → 【2.7】先检索资料库
  │   └─ 否 → 继续
  │
  ├─ 4. 【阶段二】编码（持续生效的约束）
  │   ├─ import 不跨端侧边界 【2.1】
  │   ├─ 遵循项目已有架构与命名风格 【2.2】
  │   ├─ 每个文件单一职责 【2.3】
  │   ├─ 早返回避免嵌套地狱 【2.4】
  │   ├─ 事件监听优先注册表分发 【2.5】
  │   └─ 非必要不 try，不吞异常 【2.6】
  │
  ├─ 5. 【阶段三】改动后验证（用工具确认）
  │   ├─ scan_py2_import_chain 确认 import 链完整、无循环依赖
  │   ├─ 端侧边界无混入
  │   ├─ 事件监听注册/注销配对
  │   └─ 代码风格与项目一致
  │
  └─ 任何阶段遇到不确定的决策 → 停下来问用户，不要自行决定
```
