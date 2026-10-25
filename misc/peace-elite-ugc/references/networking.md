# 网络同步：属性复制与 RPC（wiki 203 + 20457）

> 来源：官方Wiki《网络同步系统介绍》(catalog/203)、《Actor属性复制》(catalog/20457)。
> 涉及"DS数据到客户端"、"客户端通知服务器"的功能，写之前读本文。

## 总原则

- 复制方向固定是 **DS → Client 单向**。Client 改复制属性不会回传 DS——要让 DS 感知，走 RPC。
- 默认选 **RepOnce**（开销最小、触发时机最可控）。不确定就用它。
- 同一帧内多次修改同一属性，**只有最后一次会被同步**（属性同步是周期性检测）。

## 一、属性复制（DS→Client）

### 四种类型

| 类型 | 声明函数 | 触发方式 | 适用场景 |
|---|---|---|---|
| **Lifetime** | `GetReplicatedProperties` | 改值后自动比对同步 | 高频变化：坐标、血量 |
| **RepOnce**（默认推荐） | `GetReplicatedProperties`（配 `"Lazy"`） | 改值后手动 `DOREPONCE` | 绝大多数属性：阶段、积分、击杀数 |
| **InitialOnlyList** | `GetInitialOnlyListReplicatedProps` | 首次复制自动下发 | 配置类一次性数据（慎用：**后加入的Client收不到**） |
| **Blacklist** | `GetBlackListReplicatedProps` | 永不复制 | 明确不同步的继承属性 |

### 标准写法

```lua
local MyActor = {
    Health = 100,          -- Lua类成员里声明要复制的属性
    CurrentPhase = 0,
}

-- 声明复制属性
function MyActor:GetReplicatedProperties()
    return
        "Health",                          -- Lifetime：自动同步
        {"CurrentPhase", "Lazy"},          -- RepOnce：改值后需DOREPONCE
        {"d", "Lazy", "OwnerOnly"}         -- Condition：OwnerOnly只同步给Owner客户端
end

function MyActor:TakeDamage(Dmg)
    self.Health = self.Health - Dmg        -- Lifetime：直接改值即可

    self.CurrentPhase = 2
    DOREPONCE(self, "CurrentPhase")        -- RepOnce：必须紧跟修改调用，否则Client永远收不到
end
```

### DOREPONCE 两条口诀

- **Lua 声明的属性 → `DOREPONCE(self, name)`**（需配合 GetReplicatedProperties）
- **C++/蓝图预声明的属性 → `DOREPONCE_NATIVE(self, name)`**（无需声明）

其他规则：`DOREPONCE` 幂等可重复调；**不要在 Client 调**（无效）；收到时机=下次网络复制，急用可 `ForceNetUpdate()` 强制立即；"Client 没看到新值"的头号根因就是 **Lazy 属性忘了调 DOREPONCE（只赋值不同步）**。

### OnRep 监听（客户端响应变化）

```lua
function MyActor:OnRep_CurrentPhase()
    -- Client 收到新值后在这里更新UI/表现
end
```

⚠️ **各 `OnRep_xxx` 之间的先后顺序无法保证**——存在强依赖的属性（如 A 的含义依赖 B 的值）必须合并进同一个 LuaTable 一起同步。

### 选型速查

| 场景 | 用法 |
|---|---|
| 游戏阶段切换 / 积分 / 击杀数 | RepOnce |
| 玩家血量（高频） | Lifetime |
| 关卡一次性配置 | InitialOnlyList（慎用） |
| 任务进度数组 | RepOnce + Lazy |
| 用不到的继承属性 | Blacklist |

## 二、RPC

### CallUnrealRPC（点对点，双向）

```lua
-- 可靠（保证送达，开销大：低频必须送达的事件，如Tips）
UnrealNetwork.CallUnrealRPC(TargetPlayerController, TargetActor, "FunctionName", ...)
-- 不可靠（允许丢失：高频表现型——动画、粒子、流水数据）
UnrealNetwork.CallUnrealRPC_Unreliable(TargetPlayerController, TargetActor, "FunctionName", ...)
```

- DS 调用 → 发往客户端；Client 调用 → 发往 DS（同一接口，按调用端方向）。
- **Client→DS 的 ServerRPC 必须在该 Controller（或 Owner 为它的 Actor）的 Lua 里注册**：

```lua
function MyPlayerController:ServerRPC_BuyItem(ItemID)
    -- DS 侧收到申请：扣款、发货
end

function MyPlayerController:GetAvailableServerRPCs()
    return "ServerRPC_BuyItem", "ServerRPC_LikePlayer"
end
```

- DS→Client 的 ClientRPC **无需注册**。

### CallUnrealRPC_Multicast（DS 广播到所有持有该 Actor 的 Client）

```lua
-- 可靠 / Unreliable 版本同样存在
UnrealNetwork.CallUnrealRPC_Multicast(GameState, "MulticastRPC_SendEvent", EventKey, Data)

function MyGameState:MulticastRPC_SendEvent(EventKey, ...)
    -- 每个客户端都会收到，常配合本地事件系统转发
end
```

适用：击杀播报、全局结算、胜利播报。

### 顺序性

- **同一 Actor 发出的 RPC 保证对端按序接收；跨 Actor 发送不保序**。严格保序的数据固定在同一个 Actor 上发。

## 三、项目内实践建议

如果当前项目有 `Script/Lib` 基础库（本项目惯例），**跨端事件优先用 `Lib.EventSystem`**（`SendToClient / SendToAllClients / SendToServer / Broadcast`），它已把 GlobalEventComponent RPC 桥和 ServerRPC 注册封装好，不要手写 CallUnrealRPC。详见 project-lib.md。
