---
name: peace-elite-ugc
description: 和平精英绿洲启元（Oasis）UGC 的 Lua 开发知识与官方规范。凡是为和平精英/绿洲启元 UGC 项目编写或修改 Lua 脚本、蓝图脚本、GameMode/GameState/PlayerController/PlayerPawn/PlayerState/UI 逻辑，处理网络同步（属性复制、DOREPONCE、OnRep、RPC）、玩家数据存档、定时器、事件系统，或需要查询绿洲 API 手册与官方 wiki 时，都应使用本技能——即使用户没有明确提到"绿洲启元"。
---

# 和平精英绿洲启元 UGC 开发

平台 = UE4 引擎 + 和平类框架 + 和平功能专用接口库三层。本技能沉淀官方 wiki 与 API 手册的关键规范，以及项目 Lib 基础库的用法。

## 按需读取参考文档

| 任务 | 先读 |
|---|---|
| 项目内写任何功能（定时器/事件/表/随机/玩家互查） | references/project-lib.md —— **优先用项目 Lib 接口，不要重复造轮子** |
| 决定逻辑写哪端、数据放谁身上 | references/framework.md |
| 属性同步 / 复制 / RPC / 跨端通信 | references/networking.md |
| 跨对局持久化（材料、装备、金币、战绩） | references/archive.md |
| 语法细节、类型映射、容器、代理、全局API | references/lua-syntax.md |

## 编码铁律（每次写代码都检查）

1. **语法**：属性读写用 `.`；对象方法用 `:`；静态方法用 `.`。UE 全局类 U 前缀可省（`GameplayStatics`）。
2. **C++ 默认参数在 Lua 不生效**——必须显式传参，省略即 0x0（0/false/nil）。
3. **UObject 判空用 `UE.IsValid(obj)`**——被 UE 销毁的对象在 Lua 里是 invalid 而非 nil。
4. **TArray/TSet 索引 [1, N]**，不是 0 起。
5. 只能访问 UProperty 数据 / UFunction 方法；UMG 控件须勾 Is Variable。
6. 重载事件写法：`function 类名:事件名(入参)`；调父类 `当前类.SuperClass.方法(self, 入参)`。
7. Lua 异常排查：log 搜 **`[LuaException]`**。

## 端与数据的职责（速记版）

- **DS 是唯一权威端**：玩法流程、比分、击杀、胜负判断全在 DS；UI 仅存在于 Client。
- 数据存放：仅DS流程 → **GameMode**（Client拿不到）；全员可见 → **GameState**；仅自己 → **PlayerController**（也是 Client→Server 的 RPC 通道）；跟角色走 → **PlayerPawn**（Client受距离裁剪）；队友可见 → **PlayerState**（Client只能拿同队的）。
- **Client 改复制属性无效**，要让 DS 知道必须走 RPC。

## 网络同步默认套路

```lua
-- 属性复制：默认 RepOnce + Lazy
function MyActor:GetReplicatedProperties()
    return "Health", {"CurrentPhase", "Lazy"}
end
function MyActor:ChangePhase(v)
    self.CurrentPhase = v
    DOREPONCE(self, "CurrentPhase")  -- Lua属性用DOREPONCE；C++/蓝图属性用DOREPONCE_NATIVE
end
function MyActor:OnRep_CurrentPhase()  -- 客户端响应；多个OnRep顺序不保证，强依赖数据合并成一个table同步
end
```

- **只赋值不调 DOREPONCE = Client 永远收不到**（头号常见 bug）。
- RPC：`UnrealNetwork.CallUnrealRPC(pc, actor, "FnName", ...)`（可靠） / `_Unreliable`（高频表现）；Client→DS 的 ServerRPC 必须注册进 `GetAvailableServerRPCs()`。
- 项目有 Lib 时，跨端事件一律用 `Lib.EventSystem`（SendToClient/SendToAllClients/SendToServer/Broadcast），不要手写 RPC。

## 存档红线

- `UGCPlayerStateSystem.SavePlayerArchiveData / GetPlayerArchiveData` 等**仅服务器可用**，UID 需 `tonumber()`。
- **发送游戏结算数据之后不得再存档——会丢档**。存档在结算前完成。

## 性能与安全

- 传结构体用 `Vector.New(1,2,3)`，别用 `{X=1,Y=2,Z=3}`（有转换开销）。
- 缓存频繁访问的 C++/蓝图数据（每次跨界访问都有开销）。
- **禁止用 `Copy()` 缓存 UE 管理的 C++ 指针数组**（指针被 UE 释放后 DS 崩溃），要用 ToTable 快照。

## 查询官方 API 与 wiki

遇到不熟悉的类/枚举/函数，用本技能自带脚本离线查询（无需开网页）：

```bash
python "<技能目录>/scripts/gpquery.py" class UGCGameSystem --detail   # 类详情：描述/父类/可重载事件/函数/属性
python "<技能目录>/scripts/gpquery.py" class <名字或关键词>           # 搜索类
python "<技能目录>/scripts/gpquery.py" enum <关键词>                  # 枚举；struct=结构体
python "<技能目录>/scripts/gpquery.py" wiki <文章Id>                  # 读wiki原文（markdown）
python "<技能目录>/scripts/gpquery.py" wikisearch <关键词>            # 全文搜wiki文章
```

注意：和平功能接口库的函数（如 `UGCPlayerStateSystem.SavePlayerArchiveData`、`UGCGameSystem.GetAllPlayerController`）都挂在**类**上，用 `class <接口库名> --detail` 查；`func`（官方全局函数索引）很稀疏，一般用不上。

已核对过的常用 wiki 文章 Id：351=使用Lua编写玩法功能、346=Lua脚本开发指南、352=玩法开发框架介绍、203=网络同步系统介绍、20457=Actor属性复制、20052=玩家数据存档。

## 写代码的推荐顺序

1. 明确逻辑归属（DS 还是 Client？数据放哪个类？）→ framework.md
2. 查项目 Lib 是否已有现成接口 → project-lib.md
3. 不熟的 API 用 gpquery.py 查证（注意生效范围标注：服务器/客户端/双端）
4. 按 networking.md / archive.md 的红线自查一遍
