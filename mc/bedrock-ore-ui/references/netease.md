# 网易基岩版 JSON UI 接入

先找目标资源包的 `ui/_ui_defs.json`、当前 screen、客户端注册名与事件绑定。局部换肤优先替换现有控件的状态贴图、字号与间距。新建页时，把整页外壳、可滚动的页面内容和共享组件分别放在项目自己的命名空间或模板中。

## 复用随附的按钮

将 [ore_style.json](../assets/ui/ore_style.json) 放入目标资源包的 `ui/`，将[套件贴图库](../assets/textures/ui/ore_style)放入 `textures/ui/`，在现有 `ui_defs` 数组中追加一次 `ui/ore_style.json`。若项目已有同名文件或命名空间，合并前先改名并同步所有引用。随附模板继承 `common.button`。按钮底图为 5 × 7，普通与悬停的切片为 `[2,2,2,4]`，按下图的上部有两行透明像素，切片改用 `[2,4,2,2]`。

以下是一行设置的 `controls` 数组中的一个实例。把事件名换成该页实际处理的动作；新页面可在 ScreenNode 用与该事件同名的按钮绑定，沿用项目既有的点击回调签名与注册方式。

```json
{
  "help@ore_style.info_button": {
    "anchor_from": "right_middle",
    "anchor_to": "right_middle",
    "offset": [-10, 0],
    "$ore_label": "查看说明",
    "$pressed_button_name": "#settings.open_help"
  }
}
```

普通、主要、信息与危险操作分别继承 `ore_style.button`、`ore_style.primary_button`、`ore_style.info_button`、`ore_style.danger_button`。状态子控件 `normal`、`hover`、`pressed` 和 `locked` 共用标签并随按钮状态切换。禁用时通过目标项目的控件可用性绑定或 API 同步行为，在客户端验证无法点击。项目若按控件路径绑定事件，保持现有实例名与路径，并沿用该项目的事件映射。

## 分段与滑杆模板

**互斥分段**可在横向布局里各放一个 `ore_style.segment`。传入 `$ore_label`、`$pressed_button_name` 和 `$selected_binding`，后者绑定到这一档是否为当前值。每档只有一个按钮处理输入。选中装饰盖住未选的凸面，上方两行透明区透出 `$ore_row_color`，字和白线随下沉的绿色面显示。页面底色不同时传入该行色值。

**滑杆**实例继承 `ore_style.damped_slider`。像原生滑杆一样传入 `$slider_name`、`$slider_value_binding_name`、`$slider_steps_binding_name` 和目标项目使用的 TTS 绑定。连续滑杆使用默认的 `$continuous: true`；测试页的五档样例传入 `$continuous: false` 和 `$slider_steps: 5`。其他档数按业务范围调整 `slider_ticks` 的内部分隔位置。

配合 ScreenNode 实现[横向跟随](motion.md)。在 `slider_bar_default` 与 `slider_bar_hover` 两种外观中，把归一化绘制位置写到 `thumb.SetFullPosition("x", {"followType": "parent", "relativeValue": shown})`，用同一参数调用 `fill.SetFullSize("x", ...)`。两种外观各含一个 `thumb` 和 `fill`。`slider_box` 继续处理输入。数值绑定读取业务值；绘制位置使用独立变量。导航共用一个当前分类字段来绑定左侧高亮和右侧视口的可见性。

## 拼装设置页

- **视口与行**。顶部固定标题条，下方横排导航与正文。导航宽度用百分比或限宽，正文取剩余宽度。右侧滚动内容用纵向 `stack_panel` 叠行，每行用 `panel` 放文字和右侧动作。为操作列和滚动条预留宽度，让换行后的文字实际参与行高计算。字号以游戏内中文显示为准。
- **开关与分段**。复用项目的 toggle 或互斥组选项。已选项按数据源决定，分别准备选中、未选、聚焦及锁定的画面。进入页面先回显真实配置，触发一次动作后用同一配置刷新显示。
- **滑杆**。轨道、进度和手柄分层。把配置范围映射到有效拖动长度，枚举与离散数值量化到步长；标签和进度都从量化后的值推导。手机上分别验证横拖调值与纵拖滚页，拖离手柄也应正常结束。
- **适配与检查**。先核对命名空间、继承、贴图、事件以及实际滚动内容路径。可用 `mc-jsonui.validate_json_ui` 检查 JSON UI，绑定变动再核对 Python。进游戏从原入口打开，用长中文说明、最小/最大值和最后一行验收；原有保存逻辑应能在关闭重开后回显。
