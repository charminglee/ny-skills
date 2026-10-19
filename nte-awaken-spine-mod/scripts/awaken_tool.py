#!/usr/bin/env python3
"""NTE awakening-spine mod toolkit (self-contained).

Subcommands
  map    <unpacked_ctrl_dir>
         Scan BPUI_CharacterAwakenSpine_* assets and print control id ->
         Awakening dir -> SP asset.

  build  <control_base_no_ext> <out_tree> [--usmap PATH]
         Apply the full patch to one control and write the patched
         .uasset/.uexp into <out_tree>/HT/Content/UI/Blueprints/Character/Awaken/
         (out_tree should become the to-zen input directory).

  pack   <out_tree> <mod_dir> <stem> [--retoc PATH]
         to-zen into <mod_dir>/<stem>_P.utoc, then info/list/verify.

  verify <patched_base_no_ext> <mod_dir> <stem> <paks_dir> [--retoc PATH]
         Hardlink mod trio + global.* from paks_dir, to-legacy, compare against
         the patched files (uexp sha256 + export substantive fields).

Paths come from arguments or environment variables (NTE_USMAP / NTE_RETOC);
nothing is hardcoded to a machine-specific directory.
"""
import argparse, hashlib, json, os, shutil, struct, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uepkg
from usmap_unv import Usmap, R, BlobReader

AWAKEN_REL = os.path.join("HT", "Content", "UI", "Blueprints", "Character", "Awaken")


# ---------------------------------------------------------------- package utils
def export_blob(pkg, uexp, uasset_len, i):
    e = pkg.exports[i]
    s = e.serial_offset - uasset_len
    return uexp[s:s + e.serial_size]


def export_payload(pkg, uexp, uasset_len, idx):
    """Return (payload, script_bytes, script_len_header_offset)."""
    e = pkg.exports[idx]
    s = e.serial_offset - uasset_len
    pay = uexp[s:s + e.serial_size]
    last = pay.rfind(b"\x04\x0b\x53")
    assert last > 0, f"export {idx}: script tail marker missing"
    for h in range(last, -1, -1):
        L = struct.unpack_from("<i", pay, h)[0]
        if 0 < L == (last + 3) - (h + 4):
            return pay, pay[h + 4:h + 4 + L], h
    raise RuntimeError("script length header not found")


def find_export_by_name(pkg, name):
    hits = [i for i, e in enumerate(pkg.exports) if pkg.name_str(e.object_name) == name]
    assert len(hits) == 1, f"{name}: expected 1 export, got {hits}"
    return hits[0]


# ---------------------------------------------------------------- blob decoding
class Decoder:
    """Decode tagless cooked property blobs using the usmap schema."""

    def __init__(self, usmap_path):
        self.u = Usmap(usmap_path)

    @staticmethod
    def _frags_of(blob):
        r = R(blob)
        frags = []
        while True:
            packed = r.u16()
            frags.append((packed & 0x7f, bool(packed & 0x80),
                          (packed >> 9) & 0x7f, bool(packed & 0x100)))
            if frags[-1][3]:
                break
        zero_bits = sum(f[2] for f in frags if f[1])
        zm = None
        if zero_bits:
            nb = 1 if zero_bits <= 8 else (2 if zero_bits <= 16 else ((zero_bits + 31) // 32) * 4)
            mb = r.raw(nb)
            zm = [bool((mb[i // 8] >> (i % 8)) & 1) for i in range(zero_bits)]
        return frags, zm, r.p

    def type_name(self, pdata):
        return self.u.type_name(pdata)

    def decode(self, class_name, blob):
        """Yield (schema_index, 'Class.Prop', nonzero, raw_value_bytes, pdata)."""
        u = self.u
        frags, zm, hdr_end = self._frags_of(blob)
        chain, c = [], class_name
        while c in u.schemas and len(chain) < 16:
            chain.append(c)
            c = u.schemas[c]["super"]
        cum, base = [], 0
        for cn in chain:
            cum.append((base, base + u.schemas[cn]["num"], cn))
            base += u.schemas[cn]["num"]

        br = BlobReader(u, blob)
        br.p = hdr_end
        si = zi = fi = 0
        values_read = 0
        total = sum(f[2] for f in frags)

        def skip_to_values():
            nonlocal si, fi, values_read
            si += frags[fi][0]
            while frags[fi][2] == 0:
                if frags[fi][3]:
                    raise ValueError("last fragment in skip")
                fi += 1
                si += frags[fi][0]
            values_read = frags[fi][2]

        if total:
            skip_to_values()
        out = []
        for _ in range(total):
            skip, hasz, vnum, last = frags[fi]
            is_nz = (not hasz) or (not zm[zi])
            cn_ = li_ = None
            for lo, hi, cn in cum:
                if lo <= si < hi:
                    cn_, li_ = cn, si - lo
            path = pdata = None
            if cn_:
                props = u.schemas[cn_]["props"]
                if li_ in props:
                    pn, _arr, pdata = props[li_]
                    path = f"{cn_}.{pn}"
            start = br.p
            if pdata is not None:
                br.skip_val(pdata, path or "?")
            out.append((si, path, is_nz, blob[start:br.p], pdata))
            zi += 1 if hasz else 0
            si += 1
            values_read -= 1
            if values_read == 0:
                if last:
                    break
                fi += 1
                skip_to_values()
        return out


def obj_ref(pkg, raw):
    i = struct.unpack_from("<i", raw)[0]
    if i == 0:
        return None
    return pkg.import_path(-1 - i) if i < 0 else f"export#{i - 1}"


# ---------------------------------------------------------------- build
def build(control_base, out_tree, usmap_path):
    pkg = uepkg.Package(control_base + ".uasset")
    uexp = open(control_base + ".uexp", "rb").read()
    alen = len(pkg.data)

    exp_img = find_export_by_name(pkg, "Image_CharacterNormal")
    exp_n1 = find_export_by_name(pkg, "N_Spine1")
    exp_n2 = find_export_by_name(pkg, "N_Spine2")
    uber = [i for i, e in enumerate(pkg.exports)
            if "ExecuteUbergraph" in pkg.name_str(e.object_name)]
    assert len(uber) == 1, f"ubergraph exports: {uber}"
    exp_uber = uber[0]

    assert pkg.import_path(-1 - pkg.exports[exp_n2].class_index).endswith("SpineWidget")
    assert pkg.import_path(-1 - pkg.exports[exp_img].class_index).endswith("UMG/Image")

    blob2 = export_blob(pkg, uexp, alen, exp_n2)
    dec = Decoder(usmap_path)
    vals = {path: raw for _si, path, _nz, raw, _pd in dec.decode("SpineWidget", blob2) if path}
    atlas = obj_ref(pkg, vals["SpineWidget.Atlas"])
    skel = obj_ref(pkg, vals["SpineWidget.SkeletonData"])
    assert atlas and "/UISpine/Awakening/" in atlas, f"unexpected atlas: {atlas}"
    assert skel and skel.rsplit("/", 1)[-1] == atlas.rsplit("/", 1)[-1] + "_Data", \
        f"atlas/skeleton mismatch: {atlas} / {skel}"
    old_slot_fpi = struct.unpack_from("<i", vals["Widget.Slot"])[0]

    # 1) retarget N_Spine2's Tick + SetAnimation instance variable to the clone
    _, script, _hdr = export_payload(pkg, uexp, alen, exp_uber)
    name_img = pkg.name_index["Image_CharacterNormal"]
    i_n2 = pkg.name_index["N_Spine2"]
    pp_n2 = b"\x01" + struct.pack("<i", 1) + struct.pack("<i", i_n2) + struct.pack("<i", 0)
    hits, pos = [], 0
    while True:
        k = script.find(pp_n2, pos)
        if k < 0:
            break
        hits.append(k)
        pos = k + 1
    assert len(hits) == 2, f"N_Spine2 prop-pointer x{len(hits)} (want 2)"

    tick_ref = struct.pack("<i", -1 - pkg.find_import("/Script/SpinePlugin/SpineWidget/Tick"))
    anim_ref = struct.pack("<i", -1 - pkg.find_import("/Script/SpinePlugin/SpineWidget/SetAnimation"))
    kinds = []
    for k in hits:
        w = script[k:k + 64]
        fa = w.find(b"\x1c")
        assert fa >= 0, f"no FinalFunction opcode after prop pointer @{k}"
        fref = w[fa + 1:fa + 5]
        kinds.append("SetAnimation" if fref == anim_ref else
                     "Tick" if fref == tick_ref else "?")
    assert sorted(kinds) == ["SetAnimation", "Tick"], kinds

    new_script = bytearray(script)
    for k in hits:
        new_script[k + 1 + 4:k + 1 + 8] = struct.pack("<i", name_img)

    # 2) N_Spine1 role-layer animation idle1 -> idle2 (equal-length StringConst)
    idle1 = script.find(b"idle1\x00")
    assert idle1 > 0 and script.count(b"idle1\x00") == 1, "idle1 StringConst not unique"
    new_script[idle1:idle1 + 6] = b"idle2\x00"
    assert bytes(new_script) != script

    # 3) clone N_Spine2's property blob into Image_CharacterNormal
    slot_candidates = []
    for i, e in enumerate(pkg.exports):
        cls = pkg.import_path(-1 - e.class_index) if e.class_index < 0 else ""
        if "Slot" not in cls.rsplit("/", 1)[-1]:
            continue
        if struct.pack("<i", exp_img + 1) in export_blob(pkg, uexp, alen, i):
            slot_candidates.append(i)
    assert len(slot_candidates) == 1, f"slot candidates: {slot_candidates}"
    slot_fpi = slot_candidates[0] + 1

    old_cls = pkg.import_path(-1 - pkg.exports[old_slot_fpi - 1].class_index)
    assert "Slot" in old_cls.rsplit("/", 1)[-1], f"FPI {old_slot_fpi} -> {old_cls} is not a Slot"
    assert blob2.count(struct.pack("<i", old_slot_fpi)) == 1, "old slot FPI not unique in blob"
    new_blob = blob2.replace(struct.pack("<i", old_slot_fpi), struct.pack("<i", slot_fpi))

    e_img = pkg.exports[exp_img]
    e_img.class_index = -1 - pkg.find_import("/Script/SpinePlugin/SpineWidget")
    e_img.template_index = -1 - pkg.find_import("/Script/SpinePlugin/Default__SpineWidget")
    e_img.serial_size = len(new_blob)

    # 4) rebuild uexp
    order = sorted(range(pkg.export_count), key=lambda i: pkg.exports[i].serial_offset)
    pay_u, _, hdr_u = export_payload(pkg, uexp, alen, exp_uber)
    new_pay = pay_u[:hdr_u + 4] + bytes(new_script) + pay_u[hdr_u + 4 + len(script):]

    new_uexp = bytearray()
    for i in order:
        b = new_blob if i == exp_img else new_pay if i == exp_uber else export_blob(pkg, uexp, alen, i)
        pkg.exports[i].serial_size = len(b)
        new_uexp += b
    last = pkg.exports[order[-1]]
    new_uexp += uexp[last.serial_offset - alen + last.serial_size:]
    off = alen
    for i in order:
        pkg.exports[i].serial_offset = off
        off += pkg.exports[i].serial_size
    pkg.uexp_growth = 0

    ctrl_name = os.path.basename(control_base)
    out_dir = os.path.join(out_tree, AWAKEN_REL)
    os.makedirs(out_dir, exist_ok=True)
    pkg.write(os.path.join(out_dir, ctrl_name + ".uasset"))
    with open(os.path.join(out_dir, ctrl_name + ".uexp"), "wb") as f:
        f.write(bytes(new_uexp))

    return {
        "control": ctrl_name,
        "exports": {"image": exp_img, "n_spine1": exp_n1, "n_spine2": exp_n2, "ubergraph": exp_uber},
        "slot": [old_slot_fpi, slot_fpi],
        "calls": dict(zip(kinds, hits)),
        "atlas": atlas,
        "uexp": [len(uexp), len(new_uexp)],
    }


# ---------------------------------------------------------------- map
def cmd_map(ctrl_dir):
    import re
    rows = []
    for root, _dirs, files in os.walk(ctrl_dir):
        for fn in files:
            if not fn.endswith(".uasset"):
                continue
            data = open(os.path.join(root, fn), "rb").read()
            sps = set()
            for m in re.finditer(rb"[\x20-\x7e]{4,}", data):
                s = m.group().decode("ascii")
                if "/UISpine/Awakening/" in s and "_Data" not in s:
                    mm = re.search(r"/UISpine/Awakening/([^/]+)/(.+)$", s)
                    if mm:
                        sps.add((mm.group(1), mm.group(2)))
            mm = re.match(r"BPUI_CharacterAwakenSpine_(\d+)\.uasset", fn)
            if mm:
                for d, sp in sorted(sps):
                    rows.append((int(mm.group(1)), d, sp))
    for cid, d, sp in sorted(rows):
        print(f"{cid}\t{d}\t{sp}")


# ---------------------------------------------------------------- pack / verify
def _retoc(path):
    if not path:
        path = os.environ.get("NTE_RETOC")
    assert path and os.path.exists(path), "retoc path required (--retoc or NTE_RETOC)"
    return path


def cmd_pack(out_tree, mod_dir, stem, retoc_path):
    retoc = _retoc(retoc_path)
    os.makedirs(mod_dir, exist_ok=True)
    dst = os.path.join(mod_dir, stem + "_P.utoc")
    r = subprocess.run([retoc, "to-zen", "--version", "UE5_6", out_tree, dst],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-400:]
    for args in (["info"], ["list", "--path", "--size"], ["verify"]):
        rr = subprocess.run([retoc] + args + [dst], capture_output=True, text=True)
        assert rr.returncode == 0, f"{args[0]} failed: {rr.stderr[-300:]}"
    print(f"packed + verified: {dst}")


def cmd_verify(patched_base, mod_dir, stem, paks_dir, retoc_path):
    retoc = _retoc(retoc_path)
    work = os.path.join(os.path.dirname(os.path.abspath(mod_dir)),
                        "_verify_" + stem)
    stage, out = os.path.join(work, "stage"), os.path.join(work, "out")
    for d in (stage, out):
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)
    for ext in (".utoc", ".ucas", ".pak"):
        src = os.path.join(mod_dir, stem + "_P" + ext)
        os.link(src, os.path.join(stage, stem + "_P" + ext))
    for fn in os.listdir(paks_dir):
        if fn.startswith("global.") and fn.endswith((".utoc", ".ucas")):
            os.link(os.path.join(paks_dir, fn), os.path.join(stage, fn))

    r = subprocess.run([retoc, "to-legacy", "--version", "UE5_6", "--no-shaders",
                        stage, out], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-400:]

    ctrl = os.path.basename(patched_base)
    rt_base = os.path.join(out, AWAKEN_REL, ctrl)
    h = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
    assert h(patched_base + ".uexp") == h(rt_base + ".uexp"), "uexp sha256 mismatch"

    pa, pb = uepkg.Package(patched_base + ".uasset"), uepkg.Package(rt_base + ".uasset")
    assert pa.export_count == pb.export_count
    diffs = tails = 0
    for i in range(pa.export_count):
        ea, eb = pa.exports[i], pb.exports[i]
        for attr in ("class_index", "super_index", "template_index", "outer",
                     "object_name", "flags", "serial_offset", "serial_size"):
            if getattr(ea, attr) != getattr(eb, attr):
                diffs += 1
                print(f"DIFF export {i}.{attr}")
        tails += ea.tail != eb.tail
    assert diffs == 0, f"{diffs} substantive field diffs"
    print(f"roundtrip PASS: uexp identical, {pa.export_count} exports, "
          f"{tails} tail artifact diffs")
    shutil.rmtree(work)


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("map", help="list control -> awakening dir -> SP")
    p.add_argument("ctrl_dir")

    p = sub.add_parser("build", help="patch one control")
    p.add_argument("control_base")
    p.add_argument("out_tree")
    p.add_argument("--usmap", default=os.environ.get("NTE_USMAP"))

    p = sub.add_parser("pack", help="to-zen + info/list/verify")
    p.add_argument("out_tree")
    p.add_argument("mod_dir")
    p.add_argument("stem")
    p.add_argument("--retoc", default=None)

    p = sub.add_parser("verify", help="roundtrip check")
    p.add_argument("patched_base")
    p.add_argument("mod_dir")
    p.add_argument("stem")
    p.add_argument("paks_dir")
    p.add_argument("--retoc", default=None)

    a = ap.parse_args()
    if a.cmd == "map":
        cmd_map(a.ctrl_dir)
    elif a.cmd == "build":
        assert a.usmap, "usmap path required (--usmap or NTE_USMAP)"
        print(json.dumps(build(a.control_base, a.out_tree, a.usmap),
                         ensure_ascii=False, indent=1))
    elif a.cmd == "pack":
        cmd_pack(a.out_tree, a.mod_dir, a.stem, a.retoc)
    elif a.cmd == "verify":
        cmd_verify(a.patched_base, a.mod_dir, a.stem, a.paks_dir, a.retoc)


if __name__ == "__main__":
    main()
