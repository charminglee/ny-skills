# 本机 Git Bash + retoc 环境坑清单（每一条都实际踩过）

## retoc 调用

- `--aes-key` 是**全局选项**，必须放在子命令**前面**：`retoc --aes-key 0x… to-legacy …`。放在子命令后报 `unexpected argument` / usage error。
- Git Bash 下调用 Windows exe：先 `export MSYS_NO_PATHCONV=1`，然后**必须用 Windows 风格路径**（`E:\foo\bar`）；不开 PATHCONV 时 `/e/foo` 不会被转换，retoc 会报"系统找不到指定的路径"。含中文/空格的路径用 `cd` 进目录 + 相对路径最稳。
- 自己打包的模组容器**不需要** AES；读游戏容器（含 PatchPaks）**必须**带。
- `to-zen` / `to-legacy` 都要 `--version UE5_6`。

## Git Bash 工具链

- `grep` 实际是 **ugrep**：`^/` 开头的锚定模式会静默匹配 0 条（`grep -c "^/Game/"` 返回 0 但内容明明存在）。不要用 grep 做关键过滤，用 `scripts/bnames.py` 或 python 内联过滤。
- heredoc（`python - << 'EOF'`）会吃掉 `\\` 转义：python 代码里写 `'\\'` 到达解释器时只剩 `'\'` 直接语法错误。规避：用 `os.sep`、正斜杠，或把脚本写到文件再执行。
- Bash 工具的 cwd 在调用之间会被重置（输出里出现 "Shell cwd was reset"）：**每条命令都从头 `cd` + 全程绝对路径**，否则 os.walk 之类会静默扫到 0 个文件。
- 给 Windows python 传 **MSYS 风格绝对路径**（`/e/Projects/...`）会被解析成"当前盘根目录下的 `\e\Projects\...`"（报 can't open file `E:\e\Projects\...`）。给 python/脚本传路径用 `E:/Projects/...`（带盘符正斜杠）或 Windows 反斜杠形式。
- python 文档字符串里写 Windows 路径（`E:\Neverness`）会触发 `\N` unicode 转义 SyntaxError——文档字符串用 `r"""` 原始串。
- `strings` 不存在；`dotnet` 只有运行时没有 SDK（不能编译 C# 工具，UAssetGUI 是单文件 GUI 无法脚本化）——所以包编辑用 `scripts/uepkg.py`（Python）。
- Windows 的 `python`（3.12）输出/路径都用 Windows 语义；MSYS 相对路径作 argv 传入可用，但 python 内部 `os.walk` 的相对起点依赖 cwd。

## 文件系统

- **Windows 临时目录会被系统在会话中途清空**（实测：`C:\Users\12797\AppData\Local\Temp` 下刚生成的工作目录几分钟后消失）。**工作目录约定：每个模组项目一个目录 `E:\NteMod\Scripts\<项目名>\`（如 `blackbird_vfx`、`oneir_vfx`），allscan/提取/脚本/out 全放项目里**——不要在盘根建 `E:\nte_allscan`/`E:\nte_work` 这类散目录（用户明确纠正过）。
- 复制容器集（~34GB）会塞满磁盘——构建扫描目录**必须用硬链接** `os.link`（同卷零空间），见 `scripts/make_scan_dir.py`。E 盘常年 94% 占用，操作前后 `df -h /e` 检查。
- 大目录扫描（几万个 uasset）用 python 顺序读没问题，但打印进度，超时给足（600s）。

## 分析手法

- 从 .uasset 提取引用：名字表里的字符串是唯一可靠来源，`scripts/bnames.py` 提取全部/`/Game/` 开头（自动排除 Wwise 音频事件噪音）。
- "谁引用了它"反查：对提取出的全部 `.uasset` 做字节级正则搜索（b"路径片段"），按引用者目录聚合计数。注意路径片段要带边界（`042_X/` 不会匹配 `042_X_1/`），序列名要排除后缀（`(?![A-Za-z0-9_])`）。
- 对比原版 vs 模组：名字集合 `diff` 看增删；**零删除纯新增 = UAssetGUI 手改属性的典型痕迹**（旧导入留在表里不再引用）。
- 找不到某资源时先怀疑过滤器：`--filter` 按文件名匹配且大小写不敏感，路径里的文件夹名不算；换关键词（角色英文名/编号/中文名拼音如 heiyu）多跑几轮。
- **过滤器遗漏是无规律的**（伊洛伊实测）：`--filter oneir` 漏提了文件名明明含该子串的 `Oneiroi_Sequence_Fashion`、`Oneiroi_Sequence_Swimsuit` 和全部 `NS_Player_Oneir_*`/`NS_FashionPlayer_*` 特效文件，换成更长的精确前缀（`Oneiroi_Sequence`、`NS_Player_Oneir`）就能提出。**提取完按"目录里应该有什么"交叉核对，不能信单次过滤结果。**
