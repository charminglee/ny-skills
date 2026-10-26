"""皮肤战斗特效替换模组生成器（通用模板，逻辑已验证）。

用法:
  python build_vfx_swap.py            # 预览模式：只打印映射与统计，不写文件
  python build_vfx_swap.py --write    # 实际写出编辑后的 .uasset/.uexp 到 CONFIG["out"]
  python build_vfx_swap.py --verify   # 对已写出的文件做完整性校验(roundtrip + 无残留基版引用)

做新角色时只需要改下面的 CONFIG。逻辑要点见 SKILL.md；
格式细节见 references/format-notes.md。

核心手法（mid-rename）: 每个特效对象导入都是两级链
    [对象导入: 裸名, 类=NiagaraSystem, outer ->] [包导入: 完整资产路径, 类=Package, outer=0]
把"包导入"的 object_name 改写成特效源皮肤对应资产的完整路径，再把对象导入的
裸名/类改成新值即可。绝不追加、不删除导入条目——导入表结构不变，.uexp 一个字节不动。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uepkg import Package

# ============================ CONFIG（按角色填写） ============================
CONFIG = {
    # retoc to-legacy 提取输出（含 HT/Content/...，见 SKILL.md 步骤 1）
    "src": "E:/NteMod/Scripts/<项目名>/work/HT/Content",
    # 编辑结果输出根目录（将包含 HT/Content/...）
    "out": "E:/NteMod/Scripts/<项目名>/out/HT/Content",

    # ---- 特效源皮肤（效果来自哪套皮肤）----
    "src_mesh_asset": "Characters/Player/042_Blackbird_fashion1/MeshAsset_Player042_fashion1.uasset",
    "src_fx_dir": "/Game/FX/Nia/Player/FX_Player_Blackbird_Fashion_1",
    # 源皮肤特效对象的命名前缀（源皮肤后缀 = 对象名去掉此前缀）
    "src_fx_prefix": "NS_Player_BlackBird_Fashion_1_",
    # 源皮肤的大招/变身序列（用于克隆正确的类名）
    "src_seq": {
        "ultra": "sequence_pack/SkillsAnimation_Live/Blackbird/Fashion/Blackbird_skill_ultraskill_fashion1_New.uasset",
        "evolve": "sequence_pack/SkillsAnimation_Live/Blackbird/Fashion/Blackbird_evolve_sequence_fashion1.uasset",
    },

    # ---- 目标皮肤（要被换特效的 MeshAsset，相对 src 的路径）----
    "targets": [
        "Characters/Player/042_Blackbird_1/MeshAsset_Player042.uasset",
        "Characters/Player/042_Blackbird_fashion2/MeshAsset_Player042_fashion2.uasset",
        "Characters/Player/042_Blackbird_nighty/MeshAsset_Player042_nighty.uasset",
    ],
    # 目标皮肤特效的基础目录 + 对象名前缀（目标后缀 = 对象名去掉此前缀）
    "base_fx_dir": "/Game/FX/Nia/Player/FX_Player_Blackbird",
    "base_fx_prefix": "NS_Player_BlackBird_",
    # 无对应源资产、需特殊映射的目标对象名 -> 源后缀（例: 变身特效改名不同）
    "special_suffix": {"FX_Player_Blackbird_Transform": "Transform"},

    # ---- 序列覆盖: (相对 sequence_pack/SkillsAnimation_Live/<char> 的文件,
    #                 旧 FX 资产完整路径, 新 FX 资产完整路径, 用哪个源序列克隆类名) ----
    "seq_dir": "sequence_pack/SkillsAnimation_Live/Blackbird",
    "seq_swaps": [
        ("Blackbird_skill_ultraskill.uasset",
         "/Game/sequence_pack/SkillsAnimation_Live/Blackbird/Blackbird_skill_ultraskill_FX",
         "/Game/sequence_pack/SkillsAnimation_Live/Blackbird/Fashion/Blackbird_skill_Fashion1_ultraskill_FX",
         "ultra"),
        ("Fashion/Blackbird_skill_ultraskill_fashion2_New.uasset",
         "/Game/sequence_pack/SkillsAnimation_Live/Blackbird/Blackbird_skill_ultraskill_FX",
         "/Game/sequence_pack/SkillsAnimation_Live/Blackbird/Fashion/Blackbird_skill_Fashion1_ultraskill_FX",
         "ultra"),
        ("Fashion/Blackbird_skill_ultraskill_Nighty_New.uasset",
         "/Game/sequence_pack/SkillsAnimation_Live/Blackbird/Blackbird_skill_ultraskill_FX",
         "/Game/sequence_pack/SkillsAnimation_Live/Blackbird/Fashion/Blackbird_skill_Fashion1_ultraskill_FX",
         "ultra"),
        ("Blackbird_evolve_sequence.uasset",
         "/Game/sequence_pack/SkillsAnimation_Live/Blackbird/Blackbird_evolve_sequence_FX",
         "/Game/sequence_pack/SkillsAnimation_Live/Blackbird/Fashion/Blackbird_evolve_Fashion1_ultraskill_FX",
         "evolve"),
    ],
}
# ==============================================================================


def name_str(pkg, nm):
    return pkg.name_str(nm)


def is_pkg_class(pkg, im):
    return pkg.name_str(im.class_name) == "Package"


def mid_of(pkg, obj_idx):
    """对象导入所链接的资产包导入（完整路径那个）。"""
    mid = -pkg.imports[obj_idx].outer - 1
    assert pkg.name_str(pkg.imports[mid].class_name) == "Package", "expected Package mid"
    return mid


def build_source_map(cfg):
    """特效源皮肤的 后缀 -> (类包, 类名, 对象名) 映射。"""
    src = Package(os.path.join(cfg["src"], cfg["src_mesh_asset"]))
    mapping = {}
    for i in range(len(src.imports)):
        im = src.imports[i]
        if is_pkg_class(src, im):
            continue
        p = src.import_path(i)
        if not p.startswith(cfg["src_fx_dir"] + "/"):
            continue
        obj = p.split("/")[-1]
        if obj.startswith(cfg["src_fx_prefix"]):
            mapping[obj[len(cfg["src_fx_prefix"]):]] = (
                name_str(src, im.class_package), name_str(src, im.class_name), obj)
    print(f"source FX map: {len(mapping)} entries from {cfg['src_mesh_asset']}")
    return mapping


def edit_mesh_asset(cfg, mapping, rel, write):
    pkg = Package(os.path.join(cfg["src"], rel))
    n_rep = n_skip = 0
    # 第一遍: 按原始路径把对象导入按"资产包导入"(mid) 分组——
    # 同一资产常有 2 个对象导入共享一个 mid，必须一起改，否则漏改的那个解析失败
    groups = {}
    for i in range(len(pkg.imports)):
        im = pkg.imports[i]
        if is_pkg_class(pkg, im):
            continue
        p = pkg.import_path(i)
        if not p.startswith(cfg["base_fx_dir"] + "/"):
            continue
        groups.setdefault(mid_of(pkg, i), []).append(i)
    # 第二遍: 每个 mid 改名一次, 组内全部对象导入同步改写
    for mid, idxs in groups.items():
        obj = pkg.name_str(pkg.imports[idxs[0]].object_name)
        suffix = cfg["special_suffix"].get(obj)
        if suffix is None and obj.startswith(cfg["base_fx_prefix"]):
            suffix = obj[len(cfg["base_fx_prefix"]):]
        if suffix is None or suffix not in mapping:
            n_skip += 1
            continue
        cls_pkg, cls_name, new_obj = mapping[suffix]
        new_full = cfg["src_fx_dir"] + "/" + new_obj
        pkg.imports[mid].object_name = (pkg.add_name(new_full), 0)
        for i in idxs:
            im = pkg.imports[i]
            im.class_package = (pkg.add_name(cls_pkg), 0)
            im.class_name = (pkg.add_name(cls_name), 0)
            im.object_name = (pkg.add_name(new_obj), 0)
        n_rep += 1
    print(f"  {rel}: {n_rep} assets repointed, {n_skip} kept, imports={len(pkg.imports)} (unchanged)")
    if write:
        dst = os.path.join(cfg["out"], rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        pkg.write(dst, os.path.join(cfg["src"], rel[:-7] + ".uexp"), dst[:-7] + ".uexp")
    return n_rep


def edit_sequence(cfg, rel, old_fx, new_fx, ref_key, write):
    pkg = Package(os.path.join(cfg["src"], cfg["seq_dir"], rel))
    idx = None
    for i in range(len(pkg.imports)):
        if is_pkg_class(pkg, pkg.imports[i]):
            continue
        p = pkg.import_path(i)
        base = old_fx.rsplit("/", 1)[1]
        if p in (old_fx + "/" + base, old_fx):
            idx = i
            break
    assert idx is not None, f"{rel}: FX object import not found ({old_fx})"
    ref = Package(os.path.join(cfg["src"], cfg["src_seq"][ref_key]))
    ref_idx = None
    base = new_fx.rsplit("/", 1)[1]
    for i in range(len(ref.imports)):
        if is_pkg_class(ref, ref.imports[i]):
            continue
        if ref.import_path(i) == new_fx + "/" + base:
            ref_idx = i
            break
    assert ref_idx is not None, f"source sequence does not import {new_fx}"
    ref_im = ref.imports[ref_idx]
    mid = mid_of(pkg, idx)
    pkg.imports[mid].object_name = (pkg.add_name(new_fx), 0)
    im = pkg.imports[idx]
    im.class_package = (pkg.add_name(name_str(ref, ref_im.class_package)), 0)
    im.class_name = (pkg.add_name(name_str(ref, ref_im.class_name)), 0)
    im.object_name = (pkg.add_name(base), 0)
    print(f"  {rel}: FX -> {base}")
    if write:
        dst = os.path.join(cfg["out"], cfg["seq_dir"], rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        src = os.path.join(cfg["src"], cfg["seq_dir"], rel[:-7] + ".uexp")
        pkg.write(dst, src, dst[:-7] + ".uexp")


def verify(cfg):
    """完整性校验: roundtrip 字节一致 + 对象导入无基版残留。"""
    ok = True
    for rel in cfg["targets"]:
        pkg = Package(os.path.join(cfg["out"], rel))
        ok &= pkg.serialize() == pkg.data
        for i in range(len(pkg.imports)):
            im = pkg.imports[i]
            if is_pkg_class(pkg, im):
                continue
            lp = pkg.import_path(i).lower()
            base_dir = cfg["base_fx_dir"].lower()
            if lp.startswith(base_dir + "/"):
                print(f"  LEFTOVER base FX ref in {rel}: {pkg.import_path(i)}")
                ok = False
    for rel, old_fx, new_fx, _ in cfg["seq_swaps"]:
        pkg = Package(os.path.join(cfg["out"], cfg["seq_dir"], rel))
        ok &= pkg.serialize() == pkg.data
        base = old_fx.rsplit("/", 1)[1]
        found_new = False
        for i in range(len(pkg.imports)):
            if is_pkg_class(pkg, pkg.imports[i]):
                continue
            if pkg.name_str(pkg.imports[i].object_name) == new_fx.rsplit("/", 1)[1]:
                found_new = True
        if not found_new:
            print(f"  seq {rel}: new FX ref missing!")
            ok = False
    print("VERIFY:", "PASS" if ok else "FAIL")
    return ok


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    cfg = CONFIG
    write = "--write" in sys.argv
    if "--verify" in sys.argv:
        sys.exit(0 if verify(cfg) else 1)
    if not os.path.isdir(cfg["src"]):
        sys.exit(f"源目录不存在: {cfg['src']}\n先用 retoc to-legacy 提取角色资源, 见 SKILL.md 步骤 1")
    mapping = build_source_map(cfg)
    print(f"mode: {'WRITE' if write else 'DRY-RUN'}")
    for rel in cfg["targets"]:
        edit_mesh_asset(cfg, mapping, rel, write)
    for rel, old_fx, new_fx, ref_key in cfg["seq_swaps"]:
        edit_sequence(cfg, rel, old_fx, new_fx, ref_key, write)
    if write:
        print(f"\nverify pass:")
        sys.exit(0 if verify(cfg) else 1)
    else:
        print("\n(dry-run, 未写文件; 确认映射后加 --write)")


if __name__ == "__main__":
    main()
