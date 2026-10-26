"""Prepare an eye-focused study from existing corpus manifests; render report after native review."""
import argparse
import hashlib
import html
import json
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(args):
    sources = {}
    for manifest in args.manifest:
        for sample in read(manifest)["samples"]:
            sources[sample["species"]] = sample
    names = args.species.split(",")
    if len(names) != len(set(names)):
        raise ValueError("Duplicate species")
    samples = []
    for name in names:
        s = sources[name]
        geo = read(s["model"])["minecraft:geometry"][0]
        eye_bones = [b for b in geo["bones"] if any(t in b["name"].lower() for t in ("eye", "pupil", "iris", "lid"))]
        blink = []
        for file in s["animation_files"]:
            for key, clip in read(file).get("animations", {}).items():
                if "blink" in key.lower():
                    blink.append({"name": key, "file": file, "length": clip.get("animation_length"), "bones": clip.get("bones", {})})
        files = [s["model"], s["texture"], s["resolver"], *s["animation_files"],
                 *[t['file'] for t in s['layer_textures'] if t.get('file') and not t.get('missing')]]
        samples.append({k: s[k] for k in ("species", "model", "texture", "resolver", "animation_files", "layers", "layer_textures")} | {
            "eye_bones": eye_bones, "blink_candidates": blink,
            "source_sha256": {p: digest(p) for p in dict.fromkeys(files)},
            "selection_note": "Purposeful eye/face contrast sample, not representative random sample",
        })
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "native").mkdir(exist_ok=True)
    write(out / "manifest.json", {"count": len(samples), "samples": samples})
    print(json.dumps({"prepared": len(samples), "eye_bone_counts": {s['species']: len(s['eye_bones']) for s in samples}}))


def report(args):
    out = Path(args.out)
    manifest, results = read(out / "manifest.json"), read(out / "native-results.json")
    notes = read(out / "visual-notes.json")
    results = {r["species"]: r for r in results}
    sections = []
    for s in manifest["samples"]:
        name = s["species"]
        r, n = results[name], notes[name]
        if not r.get("success"):
            raise ValueError(f"Native review failed: {name}")
        sections.append(f'<section><h2>{html.escape(name)}</h2><p>{html.escape(n)}</p>'
                        f'<img loading="lazy" src="native/{name}-eyes.png" alt="{name} eyes">'
                        f'<details><summary>实际眼部 UV（名称匹配候选，需结合模型判断）</summary><img loading="lazy" src="native/{name}-uv.png"></details>'
                        f'<p class="meta">眨眼：{html.escape(str(r.get("blink", "未匹配")))} · {r.get("blink_frames", 0)} 帧 · 眼区镜位 {html.escape(str(r["camera"]))}</p></section>')
    intro = (out / "findings.md").read_text(encoding="utf-8")
    page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cobblemon 眼睛专项蒸馏</title><style>body{font-family:Segoe UI,Microsoft YaHei,sans-serif;background:#eaf0f5;color:#263749;margin:0}main{max-width:1200px;margin:auto;padding:32px}section{padding:20px;background:white;margin:24px 0;border-radius:12px}img{max-width:100%;display:block;image-rendering:pixelated}p{line-height:1.8}.meta{font-size:12px;color:#617080}pre{white-space:pre-wrap;line-height:1.8;font:inherit}summary{cursor:pointer;padding:12px}a{color:#245d96}</style><main>'
    page += f'<h1>{manifest["count"]} 只宝可梦 · 眼睛专项</h1><p>第一行：正面、斜侧、两侧面。第二行：眨眼 5 个等时刻（非自动认定半程=全闭）。下方可展开实际 UV 候选图块。原始资产及原活动项目只读；没有游戏运行验证。</p>'
    page += '<section><pre>' + html.escape(intro) + '</pre></section>'
    page += '<section><h2>拉鲁拉丝：遮挡对照</h2><p>仅在隔离研究工程中暂时隐藏头发，查看眼睛及眨眼结构；不是默认外观或游戏行为。</p><img src="native/ralts-occlusion.png"></section>' if (out/'native/ralts-occlusion.png').exists() else ''
    page += ''.join(sections)
    page += '<footer>来源：本地 Cobblemon Forge 1.5.2+1.20.1；资产作者为 Cobblemon 项目及其贡献者。模型原样导入，截图为编辑器近景/动画采样，UV 为研究提取。<a href="asset-license.txt">保留的原资产许可文本</a>。仅作本地非商业研究；公开分发前另核对署名及角色权利。Skill 本身不捆绑原资产或这些截图。</footer></main></html>'
    (out / 'report.html').write_text(page, encoding='utf-8')
    print(json.dumps({"report_species": len(sections), "notes": len(notes)}))


def verify(args):
    out = Path(args.out)
    manifest = read(out / 'manifest.json')
    hashes = {p: h for s in manifest['samples'] for p, h in s['source_sha256'].items()}
    changed = [p for p, h in hashes.items() if digest(p) != h]
    if changed:
        raise ValueError(changed)
    print(json.dumps({"unchanged_source_files": len(hashes)}))


def layers(args):
    from PIL import Image
    import math
    out = Path(args.out)
    results = {r['species']: r for r in read(out/'native-results.json')}
    records = []
    for s in read(out/'manifest.json')['samples']:
        if not s['layer_textures']:
            continue
        patches = [p for p in results[s['species']]['patches'] if 'lid' not in p['bone'].lower()]
        for t in s['layer_textures']:
            if t.get('missing'):
                continue
            im = Image.open(t['file']).convert('RGBA')
            pixels = set()
            for p in patches:
                u,v,u2,v2 = p['uv']
                pixels.update((x,y) for x in range(max(0,math.floor(min(u,u2))),min(im.width,math.ceil(max(u,u2)))) for y in range(max(0,math.floor(min(v,v2))),min(im.height,math.ceil(max(v,v2)))))
            active = sum(im.getpixel(p)[3] > 0 for p in pixels)
            records.append({'species':s['species'],'resource':t['resource'],'uv_union_pixels':len(pixels),'nonzero_alpha_in_union':active,'scope':'Named open-eye candidate UVs; charmander includes whole head faces, not isolated eye pixels. Intersection is not shader validation.'})
    write(out/'layer-coverage.json',records)
    print(json.dumps(records,ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'report', 'verify', 'layers'])
    parser.add_argument('--out', required=True)
    parser.add_argument('--manifest', action='append', default=[])
    parser.add_argument('--species', default='')
    arguments = parser.parse_args()
    globals()[arguments.mode](arguments)
