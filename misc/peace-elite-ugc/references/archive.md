# 玩家数据存档（wiki 20052）

> 来源：官方Wiki《玩家数据存档》(catalog/20052)。
> 涉及跨对局持久化（材料、装备、金币、战绩等）时读本文。

## 机制

- 玩家个人数据跨对局持久化，数据类型为 **LuaTable**（支持数字/字符串/嵌套数组字典）。
- **各玩法之间的存档数据相互隔离**，可安全使用。
- 容量：建议单玩家存档 **≤1M**；文档另一处提到 **256Kb 上限**（口径不一致）。保存大量数据前用 `GetTableDataSize` / `GetPlayerDataSize` 实测检查。
- UID 标识数据归属（获取：`UGCPawnAttrSystem.GetPlayerUID(playerPawn)`，传接口前 `tonumber()`）。

## 接口一览（均在 `UGCPlayerStateSystem`，除 GetTableDataSize 外**仅服务器可用**）

| 接口 | 签名 | 说明 |
|---|---|---|
| 保存整表 | `SavePlayerArchiveData(UID, ArchiveData, ChunkIndex?)` → boolean | 整表覆盖保存 |
| 按Key保存 | `SavePlayerArchiveDataByKey(UID, Key, Value, ChunkIndex?)` → boolean | **内部先读后写，高频场景改用整表保存** |
| 读整表 | `GetPlayerArchiveData(UID, ChunkIndex?)` → table | 读完整存档 |
| 按Key读 | `GetPlayerArchiveDataByKey(UID, Key, ChunkIndex?)` → any | Key 不存在返回 nil |
| 算大小 | `GetTableDataSize(Data)` → number | table序列化字节数（**双端可用**，失败-1） |
| 查总量 | `GetPlayerDataSize(UID)` → number | 玩家当前存档总字节（含全部分块，无数据=0） |
| 清档 | `ClearPlayerArchiveData()` | **GM指令：仅测试环境（客户端）有效，正式/PIE 无效** |
| 读离线玩家 | `GetOfflinePlayerArchiveChunkData(SourceUID, TargetUID, ChunkSeqList, Callback, CallbackSelf)` | 异步回调（bResult=="ok"）；**当前版本暂未开放** |

分块存储（ChunkIndex）：不传默认第1块；**分块功能当前版本暂未开放**，开放后按类型规划各块用途、避免混用。

## 示例

```lua
-- 存：把背包物品ID列表存档
local playerUID = UGCPawnAttrSystem.GetPlayerUID(playerPawn)
local allItemData = UGCBackPackSystem.GetAllItemData(playerPawn)
local equipSequence = {}
for _, itemData in pairs(allItemData) do
    table.insert(equipSequence, itemData.ItemID)
end
UGCPlayerStateSystem.SavePlayerArchiveData(tonumber(playerUID), equipSequence)

-- 读：进局时发放存档物品
local readArchive = UGCPlayerStateSystem.GetPlayerArchiveData(tonumber(playerUID))
for i = 1, #readArchive do
    UGCBackPackSystem.AddItem(playerPawn, readArchive[i], 1)
end

-- 按Key读写单个值
UGCPlayerStateSystem.SavePlayerArchiveDataByKey(tonumber(playerUID), "gold", 1000)
local gold = UGCPlayerStateSystem.GetPlayerArchiveDataByKey(tonumber(playerUID), "gold")

-- 保存前检查大小
local size = UGCPlayerStateSystem.GetTableDataSize(myData)
```

## 注意事项（每条都踩过坑）

1. **发送游戏结算数据之后，不要再调用 `SavePlayerArchiveData`——会丢档**。存档要在结算数据发送前完成。
2. 存档是玩家个人数据，**勿把全局数据存在同一个 UID 下**。
3. 需要清数据时把存档置 nil 即可实现清空（历史数据无法追溯）；测试环境可用 `ClearPlayerArchiveData`。
4. `SavePlayerArchiveDataByKey` 高频调用会产生大量读+写开销，攒批量用整表保存。
5. `GetOfflinePlayerArchiveChunkData` 是异步接口，在回调里处理结果，不要期望同步返回。
6. Debug 调试支持跨 DS 存档，但**仅限一次调试会话**，重启调试即重置（非持久化）。
