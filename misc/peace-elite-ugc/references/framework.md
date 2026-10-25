# 绿洲启元玩法开发框架：DS/Client 与模块职责（wiki 352）

> 来源：官方Wiki《绿洲启元玩法开发框架介绍》(catalog/352)。
> 决定"这段逻辑写在哪、这个数据放谁身上"时读本文。

## DS & Client 基本盘

- 一局玩法开始后生成 **DS（Dedicated Server）**，DS 是所有数据的**权威端**。几乎所有 Actor 在 DS 创建，然后同步到 Client 生成复制品。
- **只有 DS 的数据可信**（Client 数据可被内存篡改）。
- **玩法流程、阶段数据、击杀逻辑、比分、胜负判断都在 DS 执行和管理**；纯表现型功能（UI）由 DS 同步数据到 Client 展示。

## Actor 基础

场景实体（继承链最底层）必须继承自 Actor。Actor 含 Location/Rotation/Scale，具备网络同步职能。绑定 Lua 后可重载：
- `BeginPlay` —— 创建时触发
- `EndPlay` —— 移除时触发
- `Tick` —— 每帧触发

## 五大模块：职责与存在位置（核心）

| 模块 | DS | Client | 存什么 | 典型逻辑 |
|---|---|---|---|---|
| **GameMode** 玩法模式 | ✅ 1份 | ❌ **拿不到** | 仅DS存在的流程/阶段数据 | 玩法流程编排（与模式编辑器二选一） |
| **GameState** 数据模块 | ✅ 1份 | ✅ 每人1份复制品 | 需全员可见的全局数据 | DS全局数据同步桥梁：常驻参数（倒计时、分数面板）走属性同步；即时信息（击杀播报、胜利播报）走RPC广播 |
| **PlayerController** | ✅ 每玩家1份 | ✅ **只有自己的**复制品 | 仅自己需要知道的参数（击杀数、分数、金币） | 购买道具、仅自身可见的通知；**Client→Server交互主要途径（ServerRPC）** |
| **PlayerPawn** 角色 | ✅ 全部角色 | ⚠️ 仅附近角色（**网络裁剪**，远处可能拿不到） | 角色参数（护甲、攻击力、血量） | 用道具、放技能、播动画等角色强相关逻辑 |
| **PlayerState** | ✅ PC:PS=1:1 | ⚠️ **只有同队（TeamID相同）玩家的** | 队友需知、敌人不需知的参数 | 队伍面板血量、小地图坐标 |

**UI 系统**：**UI 仅在 Client 存在**。UI 只处理和展示 DS 同步来的数据；购买、用技能等操作由 UI 调 Controller 的 ServerRPC 向 DS 申请。UI 自身不存重要数据、不执行重要逻辑。

> 判断口诀：这个数据/逻辑谁能看见、谁执行？只在DS → GameMode；全员可见 → GameState；只有自己 → PlayerController；跟着角色走 → PlayerPawn；队友可见 → PlayerState；纯表现 → UI(Client)。

## 三个关键 ID

| ID | 含义 | 生命周期 | 获取方式 |
|---|---|---|---|
| **UID** | 玩家唯一ID，类似账号，全和平唯一 | **跨局持久** | `PlayerState.UID`、`PlayerController.PlayerUID` |
| **PlayerKey** | 玩家在单局中的临时唯一标识码 | 单局内 | `PlayerState/PlayerController/PlayerCharacter.PlayerKey` |
| **TeamID** | 队伍ID，初始由玩法上传时的匹配参数决定，可二次分队 | 单局内 | `PlayerState/PlayerController/PlayerCharacter.TeamID` |

- 存档接口用 **UID** 标识数据归属。
- **PlayerKey** 是局内找玩家实例/角色数据的主要参数（大部分"获取角色实例/角色数据"的功能都用它）。
- **TeamID** 用于敌我判断、分队、小地图队友标记、队友状态栏等。
