"""Targeted large-body texture study. Source assets remain read-only.

Uses study_shading.py native surface records. Views are local research evidence,
not redistributable replacement assets. No automatic aesthetic pass/fail score.
"""
import argparse
import html
import json
import math
import shutil
import statistics
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from study_shading import read, write, digest, pixels_for_face, face_stats

GROUPS = {
    'fur_mixed': 'arcanine ursaring electivire obstagoon typhlosion meowscarada blaziken chesnaught'.split(),
    'skin_large_surface': 'charizard blastoise dragonite feraligatr kangaskhan lapras goodra swampert machamp wailord'.split(),
    'plant': 'venusaur meganium sceptile torterra trevenant victreebel'.split(),
    'feather_wing_mixed': 'pidgeot noctowl articuno volcarona hydreigon yanmega'.split(),
    'armor_rock': 'aggron tyranitar metagross scizor skarmory rhydon gigalith golurk steelix garganacl'.split(),
}


def prepare(a):
    out=Path(a.out)
    if (out/'manifest.json').exists():
        raise ValueError('Use a new output; existing evidence will not be overwritten')
    old=read(a.manifest)
    byname={s['species']:s for s in old['samples']}
    species_files={p.stem:p for p in (Path(a.root)/'data/cobblemon/species').rglob('*.json')}
    samples=[]; hashes={}
    for group,names in GROUPS.items():
        for name in names:
            s=byname[name]
            for p in (s['model'],s['texture'],s['resolver']):
                actual=digest(p)
                if old['source_sha256'].get(p)!=actual:
                    raise ValueError('Source changed since earlier corpus: '+p)
                hashes[p]=actual
            sp=species_files[name]; data=read(sp)
            if data['height']<15: raise ValueError('Height filter failed: '+name)
            hashes[str(sp)]=digest(sp)
            row={k:s[k] for k in ('species','dex','model','texture','resolver','model_stats','layers','layer_textures')}
            row.update(study_group=group,species_file=str(sp),declared_height_dm=data['height'],base_scale=data.get('baseScale'),selection_reason='Height field >= 15 dm; purposeful material coverage, not random or a physical world-size measurement')
            for layer in row['layer_textures']:
                if layer.get('file') and not layer.get('missing'):
                    hashes[layer['file']]=digest(layer['file'])
            samples.append(row)
    out.mkdir(parents=True,exist_ok=True)
    write(out/'manifest.json',{'count':len(samples),'selection':'40 targeted large-species re-inspections from the existing 320; NOT 40 newly added species','source_manifests':[str(Path(a.manifest).resolve())],'source_sha256':hashes,'samples':samples})
    shutil.copy2(Path(samples[0]['model']).parent/'license',out/'asset-license.txt')
    print(json.dumps({'count':len(samples),'groups':{k:len(v) for k,v in GROUPS.items()},'hashes':len(hashes)},ensure_ascii=False))


def atlas_contacts(a):
    out=Path(a.out); ss=read(out/'manifest.json')['samples'];(out/'atlases').mkdir(exist_ok=True)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
    for start in range(0,len(ss),8):
        cv=Image.new('RGB',(1440,1000),'#dfe6e9');dr=ImageDraw.Draw(cv)
        for j,s in enumerate(ss[start:start+8]):
            im=Image.open(s['texture']).convert('RGBA');scale=min(330/im.width,430/im.height)
            scale=max(1,math.floor(scale)) if scale>=1 else scale
            im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.NEAREST)
            x=(j%4)*360+10;y=(j//4)*500+42
            cv.paste(im,(x,y),im);dr.text((x,y-32),f"{s['species']} {Image.open(s['texture']).size}",font=font,fill='#243844')
        cv.save(out/'atlases'/f'{start//8+1:02}.png')
    print(json.dumps({'atlas_pages':math.ceil(len(ss)/8)}))


def focus(a):
    out=Path(a.out); ss={s['species']:s for s in read(out/'manifest.json')['samples']}
    selections=read(out/'focus-selection.json');(out/'focus').mkdir(exist_ok=True)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16);records=[]
    for entry in selections:
        name=entry['species'];s=ss[name];im=Image.open(s['texture']).convert('RGBA');native=read(out/'surfaces'/f'{name}.json')
        cv=Image.new('RGB',(1200,320+len(entry['cubes'])*220),'#dfe6e9');dr=ImageDraw.Draw(cv)
        view=Image.open(out/'native'/f'{name}-shading.png');cv.paste(view.crop((0,0,1024,284)),(0,20))
        dr.text((8,0),name+' / native bind pose, texture-only; UV patches below',font=font,fill='#243844')
        for row,choice in enumerate(entry['cubes']):
            cube=choice['cube'];ff=[f for f in native['surfaces'] if f['cube']==cube]
            if not ff:raise ValueError((name,cube))
            for col,key in enumerate(['north','east','south','west','up','down']):
                f=next((f for f in ff if f['face']==key),None)
                if not f:continue
                x0,y0,x1,y1=f['uv'];rect=(math.floor(min(x0,x1)),math.floor(min(y0,y1)),math.ceil(max(x0,x1)),math.ceil(max(y0,y1)))
                patch=im.crop(rect)
                if x1<x0:patch=patch.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                if y1<y0:patch=patch.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                if f['rotation']:patch=patch.rotate(-f['rotation'],expand=True)
                scale=max(1,min(184//patch.width,145//patch.height))
                patch=patch.resize((patch.width*scale,patch.height*scale),Image.Resampling.NEAREST)
                if patch.width>184 or patch.height>145:patch.thumbnail((184,145),Image.Resampling.NEAREST)
                x=col*200+8;y=320+row*220;cv.paste(patch,(x,y),patch)
                stats=face_stats(pixels_for_face(im,f))
                dr.text((x,y+150),f"#{cube} {f['bone']}"[:24],font=font,fill='#243844')
                dr.text((x,y+169),f'{key} {abs(x1-x0):g}x{abs(y1-y0):g}',font=font,fill='#243844')
                if stats:dr.text((x,y+188),f"{stats['colors']} cols / main {stats['dominant_fraction']:.0%}",font=font,fill='#243844')
                records.append({'species':name,'region':choice['region'],'cube':cube,'face':key,'bone':f['bone'],'uv':f['uv'],'stats':stats})
        cv.save(out/'focus'/f'{name}.png')
    write(out/'focus-metrics.json',records)
    print(json.dumps({'focus_species':len(selections),'faces':len(records)}))


def report(a):
    out=Path(a.out);m=read(out/'manifest.json');notes=read(out/'visual-notes.json');summary=read(out/'summary.json')
    summary['limitations']='Purposeful 40-species large-body subset of previous 320; internal/shared/hidden faces included; not species-independent votes, material segmentation, or a style score.'
    write(out/'summary.json',summary)
    ms=[s['model_stats'] for s in m['samples']]
    stats={'species':len(ms),'cubes':sum(s['cubes'] for s in ms),'bones':sum(s['bones'] for s in ms),'planar_cubes':sum(s['planar_cubes'] for s in ms),'median_cubes':statistics.median(s['cubes'] for s in ms),'resolution_histogram':dict(Counter('x'.join(map(str,s['resolution'])) for s in ms)),'base_layer_species':[s['species'] for s in m['samples'] if s['layers']]}
    stats['supplemental_views']=sum(Image.open(p).height//500*2 for p in (out/'closeups').glob('*.png'))
    stats['focus_cubes']=sum(len(r['cubes']) for r in read(out/'focus-selection.json'))
    stats['focus_faces']=len(read(out/'focus-metrics.json'))
    write(out/'large-summary.json',stats)
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>较大体型 40 只 · 材质专项</title><style>body{margin:0;background:#eef2f4;color:#243844;font:16px/1.7 system-ui}main{max-width:1250px;margin:auto;padding:24px}section{background:white;padding:20px;margin:20px 0;border-radius:12px}img{max-width:100%;image-rendering:pixelated}pre{white-space:pre-wrap;font:inherit}summary{cursor:pointer;padding:10px}a{color:#245f8e}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:8px;text-align:left}</style><main><h1>40 只较大体型宝可梦 · 模型与材质专项</h1>'
    page+='<p>本地 Cobblemon Forge 1.5.2+1.20.1。既有 320 样本中的定向复查，不是新增 40 个物种。绑定姿势基础贴图，各四镜位开关面光照；不冒充游戏最终效果或新动画研究。</p><section><pre>'+html.escape((out/'FINDINGS.md').read_text(encoding='utf-8'))+'</pre></section>'
    page+='<section><h2>40 只整体观察与原图集</h2>'
    for i,note in enumerate(notes['pages'],1):
        page+=f'<details><summary>第 {i} 组 · {html.escape(note)}</summary><img loading="lazy" src="contacts/{i:02}.png"><img loading="lazy" src="atlases/{i:02}.png"></details>'
    page+='</section><section><h2>材料部位 UV 精查</h2>'
    for name,note in notes['focus'].items():
        page+=f'<details><summary>{name} · {html.escape(note)}</summary><img loading="lazy" src="focus/{name}.png"><a href="native/{name}-shading.png">开关面光照完整对照</a> · <a href="closeups/{name}.png">高角度及部位近景（周边模型保留，部分目标可能被遮挡）</a></details>'
    page+='</section><section><h2>逐只观察记录</h2><table><tr><th>物种</th><th>身高数据 / 块数 / 图集</th><th>观察</th></tr>'
    for s in m['samples']:
        name=s['species'];st=s['model_stats'];page+=f'<tr><td><a href="native/{name}-shading.png">{name}</a></td><td>{s["declared_height_dm"]/10:g}m / {st["cubes"]} / {st["resolution"]}</td><td>{html.escape(notes["species"][name])}</td></tr>'
    page+='</table></section><section><h2>薄片高角度补查</h2>'+''.join(f'<a href="closeups/{n}.png">{n}</a> · ' for n in ['meganium','yanmega','noctowl','articuno'])+'</section><footer>来源与作者：Cobblemon 项目及贡献者；模型/贴图未修改，截图和 UV 裁片仅作本地非商业研究。<a href="asset-license.txt">完整原许可</a>。Skill 只保存通用规则与工具，不打包源资产或截图。身高字段与 baseScale 不等于本报告渲染时已应用的游戏物理尺寸。</footer></main></html>'
    (out/'report.html').write_text(page,encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['prepare','atlas_contacts','focus','report']);p.add_argument('--out',required=True);p.add_argument('--manifest');p.add_argument('--root');a=p.parse_args();globals()[a.mode](a)
