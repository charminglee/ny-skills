# 绿洲启元 Lua 脚本开发规范（wiki 351 + 346）

> 来源：官方Wiki《使用Lua编写玩法功能》(catalog/351)、《绿洲启元Lua脚本开发指南》(catalog/346)。
> 写任何绿洲启元 Lua 代码前先过一遍本文的"铁律"部分。

## 脚本创建

可编程蓝图上方有 **Lua 按钮**，点击后在工程 `Script` 文件夹对应路径下创建同名 Lua 脚本。Lua 脚本监听对应蓝图事件、调用蓝图函数。

## 铁律（最容易踩的坑）

1. **C++ 默认参数在 Lua 中不生效**（C++ 默认值是编译期生效，Lua 是运行期）。调用 C++ 接口必须显式传参；省略的参数会传 `0x0`（number=0、bool=false、指针=nil、结构体内部字段同理）。
2. **被 UE 销毁的 UObject 在 Lua 里是 invalid object 而不是 nil**。判空必须用 `UE.IsValid(obj)`（等价全局 `IsValid`）。Lua 持有的 UObject 引用在对象销毁前建议手动置 nil。
3. **TArray / TSet 在 Lua 中的索引区间是 [1, N]**，不是 C++ 的 [0, N-1]。
4. Lua 只能访问 **UProperty 数据** 和 **UFunction 方法**（UE4 反射系统）。蓝图里变量/方法/代理列表都可在 Lua 访问；BPActor 中 Component 默认都是变量；**BPUMG 中子控件必须勾选 `Is Variable`** 才能在 Lua 访问。
5. Lua 执行异常输出到 log，关键词 **`[LuaException]`**——排查问题先搜这个。

## 基础语法

- 对象成员属性读/写：**点(.)** —— `local n = Pawn.PlayerName; Pawn.PlayerName = "Test"`
- 对象成员方法：**冒号(:)** —— `Pawn:K2_SetActorLocation(Vector(0,0,0))`
- 类静态方法：**点(.)** —— UE 全局类 U 前缀可省：`UGameplayStatics` → `GameplayStatics.GetPlayerCharacter(self, 0)`
- 枚举：`Enum.EnumItem`（仅限 C++ 声明的枚举）—— `Widget:SetVisibility(ESlateVisibility.Visible)`

### 可重写（重载）函数

- C++ 中 `UFUNCTION` 宏带 `BlueprintNativeEvent` / `BlueprintPure` 标记的函数可重写。
- **蓝图中定义的函数均可重写**。
- 调用父类实现：`self.SuperClass.ReceiveBeginPlay(self)`（等同 C++ 的 `Super::`）。

```lua
local UGCGameMode = {}
function UGCGameMode:ReceiveBeginPlay()
    self.SuperClass.ReceiveBeginPlay(self)
end
```

## 数据类型映射

| C++ 类型 | Lua 类型 |
|---|---|
| bool / uint8:1 | boolean |
| Enum / EnumAsByte<> | number (integer) |
| [u]int8/16/32/64 | number (integer) |
| float / double | number (float) |
| FString / FText / FName | string |
| TArray / TSet / TMap | userdata（自定义封装，带元表） |
| UStruct | userdata（引用传递） |
| UObject / WeakObjectPtr<> | userdata |

### 结构体

- Lua 访问到的结构体是 userdata（带元表），**引用传递**。
- 赋值兼容 userdata（**推荐**）和 table 两种：table 赋值时 Key 为字段名、可部分赋值，未赋值字段用 0x0 填充。

```lua
object.ColorAndOpacity = t1;                    -- userdata（推荐）
object.ColorAndOpacity = {R=1, G=2, B=3, A=1};  -- table 兼容写法
object.ColorAndOpacity = {R=1, A=1};            -- 部分赋值 = FLinearColor(1,0,0,1)
```

### 容器（TArray / TSet / TMap）

| 操作 | TArray | TSet | TMap |
|---|---|---|---|
| 添加 | Add / AddUnique / Push / Insert(Index,Item) | Add | Add(Key,Value) |
| 移除 | Remove / RemoveAt(Index) / Pop | Remove / RemoveAt | Remove(Key) |
| 访问 | `[Index]` / Get(Index) | `[Index]` / Get(Index) | `[Key]` / Get(Key) |
| 修改 | `[Index]=Item` / Set | `[Index]=Item` / Set | `[Key]=Value` / Set |
| 查找 | Find / Contains | Find / Contains / IsValidIndex | Find(Key) |
| 清空 | Empty / Reset([Slack]) | 同左 | 同左 |
| 数量 | Num()（`#arr` 亦可） | Num() | Num() |

遍历统一用 `pairs()`：TArray/TSet 的 k 为索引 [1,N]；TMap 的 k 为 Key、v 为 Value。

### 代理（委托）

- **单播**（C++ 前缀 `DECLARE_DELEGATE`，如 `Button.OnMouseButtonDownEvent`）：`Bind(func[, param])` / `UnBind()` / `Execute(...)`。多次 Bind 会覆盖。
- **多播**（C++ 前缀 `DECLARE_DYNAMIC_MULTICAST_DELEGATE`，如 `Button.OnClicked`）：
  - `Add(func[, param])`——以 func 为 Key 去重（同 func 不同 param 会覆盖）
  - `AddInstance(func[, param])`——以 func+param 共同为 Key
  - `Remove(func[, param])` / `RemoveAll()` / `Broadcast(...)`
  - 匿名函数绑定后无法通过 Remove 移除。
- 创建代理（主要用于 SetTimer，生命周期跟随 Object）：`ObjectExtend.CreateDelegate(Object, func)` / `ObjectExtend.DestroyDelegate(delegate)`。

```lua
self.TimerDelegate = ObjectExtend.CreateDelegate(self, function()
    ObjectExtend.DestroyDelegate(self.TimerDelegate)
end)
self.TimerHandle = KismetSystemLibrary.K2_SetTimerDelegateForLua(self.TimerDelegate, self, 3, false)
```

### 方法返回值

- 返回值一律**值拷贝**（UObject 例外：返回的是指针值）。
- **非 const 引用参数作为额外返回值，依次排在 return 后面**：

```lua
Result, OutParam1, OutParam2 = DemoWidget:GetDoubleParam(OutParam1, OutParam2)
```

## 全局 API 速查

- `CreateUIWidget(bp_lua, ClassFullPath)` / `CreateUIWidgetWithClass(bp_lua, Class)` —— 创建 UI 对象
- `LoadObject(路径)` / `LoadClass(路径)` —— 加载对象/类
- `UE.IsValid(Object)`、`UE.IsA(Object, Class)`、`UE.FindObject / FindObjectFast / StaticLoadObject`
- `UE.GetName / GetFullName / GetOuter / LuaGetPathName`、`UE.ToTable(Data)`
- `GetClassName(Object)`、`IsObject(Object, bEvenNullptr)`、`WeakObjectPtr(Object)`
- `GetWorldContext(InObj)` —— 需要 WorldContext 参数的地方用它的返回值
- `totable(Data)` —— 调试用：UStruct/容器转 table 打印。**Shipping 下仅支持容器**，别在正式逻辑里依赖它
- `CheckData(flag)`、`ShowPlatformMessageBox(Title, Message)` —— 仅 Dev 有效

## 性能与安全清单

1. 频繁传结构体给 UE 时**用结构体构造（`Vector.New(1,2,3)`）而非 table**（`{X=1,Y=2,Z=3}` 有转换开销）。
2. **缓存频繁访问的数据**——每次跨 Lua/C++ 边界访问属性都有查询开销。
3. **禁止用 `Copy()` 缓存 UE 管理的 C++ 指针数组**——指针可能被 UE 释放，访问时 DS 崩溃。要用 ToTable 方式做快照缓存。（官方给过的错误案例：`self.X = CheckActorArray.OverlapActorList:Copy()`）
4. `totable` 只用于调试和特殊需求（Shipping 行为不同）。
