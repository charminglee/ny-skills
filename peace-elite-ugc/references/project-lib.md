# 项目 Lib 基础库（Script/Lib）——写代码优先用它的接口

> 本项目（及采用同样模板的项目）在 `src/<项目名>/Script/Lib/` 有一套自研基础库。
> **写任何功能前先查这里是否已有对应能力，不要重复造轮子、不要绕开它手写底层调用。**
> 若当前项目没有 Lib，可参照本文的职责划分自行搭建。

Lib 通过 `Lib.lua` 挂为**全局变量 `Lib`**（启动时已 require，使用时无需再 require）。模块内部加载用 `UGCGameSystem.UGCRequire("Script.Lib.Utils.EventSystem")` 形式。
另有全局变量 `GameMode` / `GameState`（由 Lib.lua 的 metatable 拦截 `UGCGameSystem.GameMode=x` 赋值自动同步）。

## Lib 核心（Lib.lua）

| 接口 | 说明 |
|---|---|
| `Lib.CreateTimer(秒, 是否循环, 回调, obj, ...)` → FTimerHandle | 定时器（封装 UGCTimerUtility；obj为回调所在对象，静态函数传nil） |
| `Lib.RemoveTimer(timer)` | 移除定时器 |
| `Lib.IsServer()` | 是否服务端（优先 `GameState:HasAuthority()`） |
| `Lib.IsPIE()` / `Lib.IsDebug()` | 环境判断 |
| `Lib.GetClass(clsPath)` | 带缓存的类加载，路径从 `Asset/` 开始（自动拼根路径） |
| `Lib.GetPlayerControllerClass()` / `GetPlayerStateClass()` / `GetPlayerPawnClass()` | 项目三个玩家蓝图类：UGCPlayerController/State/Pawn |
| `Lib.IsPlayer(actor)` | 判断Actor是否玩家（含Owner判断） |
| `Lib.ToPlayerController(obj)` / `ToPlayerState(obj)` / `ToPlayerPawn(obj)` | 玩家对象互转；支持 PlayerKey、UID 和 Owner 为玩家的 Actor，数字优先按 PlayerKey 查找；Controller 的 UID 查询仅服务端支持 |
| `Lib.ToTable(obj)` | UE对象转table（目前仅支持 ItemDefineID） |
| `Lib.ToItemDefineId(obj, customizedType)` | 从 ItemDefineID 数组中按 customizedType 筛选 |
| `Lib.LONG_ROOT_PKG_PATH` | 根目录长路径（以 / 结尾） |

## Lib.EventSystem（事件总线，双端）——跨端事件首选

```lua
local EventSystem = Lib.EventSystem

-- 本地事件
EventSystem.Listen("KillZombie", self.OnKillZombie, self)   -- 监听（自动去重）
EventSystem.Unlisten("KillZombie", self.OnKillZombie, self) -- 移除
EventSystem.UnlistenByOwner(self)                           -- 移除该对象全部监听
EventSystem.Dispatch("KillZombie", playerKey, zombieId)     -- 本地触发（pcall保护+快照遍历，派发中增删安全）

-- 跨端事件（底层自动走 GlobalEventComponent 的 RPC，ServerRPC 已注册好）
EventSystem.SendToClient(player, "EventName", ...)          -- 服务端→指定玩家（传PC/PS/Pawn均可，自动换算PC）
EventSystem.SendToAllClients("EventName", ...)              -- 服务端→全部客户端
EventSystem.SendToServer("EventName", ...)                  -- 客户端→服务端
EventSystem.Broadcast("EventName", ...)                     -- 本地+对端全发
EventSystem.Broadcast_SinglePlayer(player, "EventName", ...) -- 本地+指定玩家客户端
```

**不要**再手写 `UnrealNetwork.CallUnrealRPC` 做事件转发——除非需要 Multicast 广播或不可靠通道的特殊场景。

## Lib.Table（表工具）

- 通用：`SetDefault(t,key,def)` / `Map(t,fn)` / `Merge(t1,t2)` / `IsEmpty(t)` / `Copy(浅)` / `DeepCopy(深,处理循环引用)` / `Filter(t,fn)` / `FindKey(t,val)` / `Keys(t)` / `Values(t)` / `Count(t,val)` / `Remove(t,val)`
- 列表：`FromList(list)` / `Slice(list,from,to)` / `Concat(l1,l2)`（带.n） / `Index(list,val)` / `Contain(list,val)` / `Unique(list)`

## Lib.Math / Lib.Random

- `Math.Clamp(v,min,max)`、`Math.Chance(c)`（c概率返回true）、`Math.Round(v,小数位)`
- `Random.GenString(len=16)`、`Random.Shuffle(list)`、`Random.Pick(list,n)`（n=1返回单元素，n>1返回列表）

## 组件（Component/）

- `GlobalEventComponent` —— EventSystem 的 RPC 桥（挂在 PlayerController 上，字段 `pc.GlobalEventComponent`；ClientRPC/ServerRPC/Multicast_FromEventSystem → Dispatch）
- `BaseComponent` —— 组件基类（BeginPlay 时缓存 `self.owner`）

## LuaHelperExtend/（UE封装与类型声明）

- `Classes/UGCGameSystem.lua`：玩家互查全家桶——`GetAllPlayerController(NotIgnorePureSpectator)` / `GetAllPlayerPawn()` / `GetAllPlayerState()`、`GetPlayerKeyByxxx`、`GetPlayerControllerByxxx`、`GetPlayerPawnByxxx`、`GetPlayerStateByxxx`、`GetUIDByxxx`（xxx∈PlayerKey/PlayerPawn/PlayerState/PlayerController/UID）、`GetLocalPlayerController/Pawn/State`、`GetGameMode/GetGameState`、观战控制（EnterSpectating等）
- `Classes/UE.lua`：`UE.IsA / FindObject / FindObjectFast / LoadObject / StaticLoadObject / LoadClass / GetName / GetFullName / GetOuter / IsValid / IsObject / ToTable`
- `Classes/ObjectExtend.lua`：`CreateDelegate(Object, func)` / `DestroyDelegate(delegate)`
- `Classes/UKismetSystemLibrary.lua`：268 个 Kismet 系统函数包装（PrintString、GetGameTimeInSeconds、ExecuteConsoleCommand 等）
- `Globals.lua`：全局函数声明（LoadObject/LoadClass/CreateUIWidget/totable 等，---@meta）

## 项目目录惯例

- `Script/Blueprint/` —— 蓝图 Lua 脚本（UGCGameMode.lua、UGCPlayerController.lua 等）
- `Script/Blueprint/Managers/` —— 玩法管理器（PlayerDataManager 等）
- `Script/Lib/` —— 本基础库
