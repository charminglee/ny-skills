r"""构建 retoc 扫描目录：把游戏全部容器硬链接到 <项目目录>\allscan（不占额外磁盘空间）。

用法: python make_scan_dir.py [项目目录] [游戏根目录]
默认: 项目 E:\NteMod\Scripts\new_project ，游戏根 E:\Neverness To Everness
      即 E:\NteMod\Scripts\new_project\allscan
约定: 每个模组项目一个目录（如 E:\NteMod\Scripts\oneir_vfx），allscan/提取/脚本/out
      全放项目里，不要在盘根建扫描目录。

要点（为什么这样做）:
- 新皮肤/新内容在 PatchPaks/ 和 TagPatchPaks/ 热更容器里，只扫 Paks 会漏；
- 必须用硬链接(os.link)而不是复制——完整容器集约 34GB，复制会塞满磁盘；
- global.ucas/global.utoc 是未加密的包存储，retoc 解析导入包名需要它；
  取 PatchPaks 里的（较新），全目录只能有一份 global，否则名字解析混乱。
"""
import os
import shutil
import sys

PROJECT = sys.argv[1] if len(sys.argv) > 1 else r"E:\NteMod\Scripts\new_project"
GAME_ROOT = sys.argv[2] if len(sys.argv) > 2 else r"E:\Neverness To Everness"
DST = os.path.join(PROJECT, "allscan")
CONTENT = os.path.join(GAME_ROOT, "Client", "WindowsNoEditor", "HT", "Content")
SUBS = ("Paks", "PatchPaks", "TagPatchPaks")

if os.path.exists(DST):
    shutil.rmtree(DST)
os.makedirs(DST)

# 唯一一份 global：用 PatchPaks 的（热更后更新）
for f in ("global.ucas", "global.utoc"):
    shutil.copy(os.path.join(CONTENT, "PatchPaks", f), os.path.join(DST, f))

n = 0
for sub in SUBS:
    d = os.path.join(CONTENT, sub)
    for f in os.listdir(d):
        if f.startswith("global"):
            continue
        if f.endswith((".utoc", ".ucas", ".pak", ".sig")):
            s = os.path.join(d, f)
            t = os.path.join(DST, f)
            if not os.path.exists(t):
                os.link(s, t)   # 硬链接：同卷零空间占用
            n += 1
print(f"linked {n} containers -> {DST}")
