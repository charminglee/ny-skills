"""Read-only whole-form texture study: prepare sources, analyze native UVs, build evidence."""
import argparse
import colorsys
import hashlib
import html
import json
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def write(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def prepare(a):
    samples = {}
    for p in a.manifest:
        for s in read(p)['samples']:
            samples[s['species']] = s
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for s in samples.values():
        for p in [s['model'], s['texture'], s['resolver']]:
            hashes[p] = digest(p)
        for layer in s.get('layer_textures', []):
            if layer.get('file') and not layer.get('missing'):
                hashes[layer['file']] = digest(layer['file'])
    ordered = sorted(samples.values(), key=lambda s: s['dex'])
    write(out/'manifest.json', {'count': len(ordered), 'selection': 'Reanalysis of existing distinct species, NOT newly added species', 'source_manifests': a.manifest, 'source_sha256': hashes, 'samples': ordered})
    license_path = Path(ordered[0]['model']).parent/'license'
    shutil.copy2(license_path, out/'asset-license.txt')
    print(json.dumps({'samples': len(ordered), 'source_files': len(hashes)}))


def lightness(rgb):
    linear = [v/255/12.92 if v/255 <= .04045 else ((v/255+.055)/1.055)**2.4 for v in rgb]
    y = sum(w*v for w, v in zip((.2126, .7152, .0722), linear))
    return 116*y**(1/3)-16 if y > .008856 else 903.3*y


def family(rgb):
    h, s, v = colorsys.rgb_to_hsv(*(x/255 for x in rgb))
    return 'neutral' if s < .15 else str(int(h*12)%12)


def pixels_for_face(im, f):
    # Native vertex UVs preserve cube mirror/face orientation; exact f.uv sets coverage.
    vv = f['vertices']; u0, v0 = vv[0]['uv']; u1,v1=vv[1]['uv']; u2,v2=vv[2]['uv']
    du1,dv1,du2,dv2=u1-u0,v1-v0,u2-u0,v2-v0
    det=du1*dv2-du2*dv1
    if abs(det)<1e-9: return []
    uv=f['uv']; x0,x1=sorted((uv[0],uv[2])); y0,y1=sorted((uv[1],uv[3]))
    rw,rh=f.get('resolution', im.size)
    x0,x1=x0*im.width/rw,x1*im.width/rw; y0,y1=y0*im.height/rh,y1*im.height/rh
    data=[]
    for y in range(max(0,math.floor(y0)),min(im.height,math.ceil(y1))):
        for x in range(max(0,math.floor(x0)),min(im.width,math.ceil(x1))):
            rgb=im.getpixel((x,y))
            if rgb[3]<128: continue
            dx,dy=x+.5-u0,y+.5-v0
            a=(dx*dv2-dy*du2)/det; b=(du1*dy-dv1*dx)/det
            p=[vv[0]['p'][j]+a*(vv[1]['p'][j]-vv[0]['p'][j])+b*(vv[2]['p'][j]-vv[0]['p'][j]) for j in range(3)]
            data.append({'xy':(x,y),'rgb':rgb[:3],'L':lightness(rgb[:3]),'family':family(rgb[:3]),'p':p})
    return data


def face_stats(data):
    if not data: return None
    colors=Counter(p['rgb'] for p in data); pix={p['xy']:p for p in data}
    edges=[]; equal=0
    for (x,y),p in pix.items():
        for q in ((x+1,y),(x,y+1)):
            if q in pix:
                edges.append(abs(p['L']-pix[q]['L']))
                equal+=p['rgb']==pix[q]['rgb']
    isolated=0
    for (x,y),p in pix.items():
        neighbors=[pix[q] for q in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)) if q in pix]
        if len(neighbors)>=2 and all(q['rgb']!=p['rgb'] for q in neighbors): isolated+=1
    return {'pixels':len(data),'colors':len(colors),'dominant_fraction':colors.most_common(1)[0][1]/len(data),'mean_L':sum(p['L'] for p in data)/len(data),'equal_neighbor_fraction':equal/len(edges) if edges else None,'mean_neighbor_delta_L':sum(edges)/len(edges) if edges else None,'isolated_exact_color_fraction':isolated/len(data)}


def analyze(a):
    out=Path(a.out); manifest=read(out/'manifest.json'); records=[]
    (out/'records').mkdir(exist_ok=True)
    for s in manifest['samples']:
        native=read(out/'surfaces'/f"{s['species']}.json")
        im=Image.open(s['texture']).convert('RGBA'); geo=read(s['model'])['minecraft:geometry'][0]
        res=(geo['description']['texture_width'],geo['description']['texture_height'])
        rows=[]; pairs=[]; vertical=[]; union=set(); by_cube=defaultdict(dict)
        for f in native['surfaces']:
            f['resolution']=res
            data=pixels_for_face(im,f)
            stats=face_stats(data)
            if not stats: continue
            union.update(p['xy'] for p in data)
            row={k:f[k] for k in ('cube','bone','face','uv','normal','area')};row.update(stats);rows.append(row)
            by_cube[f['cube']][f['face']] = (f,data)
            if len(data)>=12 and abs(f['normal'][1])<.5:
                families=Counter(p['family'] for p in data); main,n=families.most_common(1)[0]
                selected=[p for p in data if p['family']==main]
                ys=[p['p'][1] for p in data]; lo,hi=min(ys),max(ys)
                if hi-lo>1e-4 and n/len(data)>=.55:
                    top=[p['L'] for p in selected if p['p'][1]>=lo+(hi-lo)*.70]
                    bottom=[p['L'] for p in selected if p['p'][1]<=lo+(hi-lo)*.30]
                    if len(top)>=3 and len(bottom)>=3:
                        vertical.append({'cube':f['cube'],'bone':f['bone'],'face':f['face'],'hue_bin':main,'coverage':n/len(data),'top_L':sum(top)/len(top),'bottom_L':sum(bottom)/len(bottom),'delta':sum(top)/len(top)-sum(bottom)/len(bottom)})
        for cube,faces in by_cube.items():
            for first,second in [('up','down'),('north','south')]:
                if first not in faces or second not in faces: continue
                f1,d1=faces[first];f2,d2=faces[second]
                # Restrict to nearly axis-aligned faces, but do NOT assert material identity.
                axis,sign=(1,1) if first=='up' else (2,-1)
                if f1['normal'][axis]*sign<.9 or f2['normal'][axis]*sign>-.9:continue
                if min(len(d1),len(d2))<8: continue
                c1=Counter(p['family'] for p in d1);c2=Counter(p['family'] for p in d2)
                common=set(c1)&set(c2)
                if not common:continue
                h=max(common,key=lambda h:min(c1[h]/len(d1),c2[h]/len(d2)))
                if min(c1[h]/len(d1),c2[h]/len(d2))<.55:continue
                v1=[p['L'] for p in d1 if p['family']==h];v2=[p['L'] for p in d2 if p['family']==h]
                pairs.append({'cube':cube,'bone':f1['bone'],'faces':[first,second],'hue_bin':h,'coverage':[c1[h]/len(d1),c2[h]/len(d2)],'means':[sum(v1)/len(v1),sum(v2)/len(v2)],'delta':sum(v1)/len(v1)-sum(v2)/len(v2)})
        r={'species':s['species'],'sampled_faces':len(rows),'unique_used_texels':len(union),'used_colors':len({im.getpixel(p) for p in union}),'faces':rows,'same_hue_opposite_face_candidates':pairs,'same_hue_vertical_candidates':vertical,'limitations':'All nontransparent mapped faces including internal and hidden faces; hue similarity is NOT proof of same material. Candidate statistics are descriptive, not whole-model light direction.'}
        write(out/'records'/f"{s['species']}.json",r);records.append(r)
    allfaces=[f for r in records for f in r['faces'] if f['pixels']>=12]
    import statistics
    summary={'species':len(records),'sampled_faces':sum(r['sampled_faces'] for r in records),'candidate_face_min_pixels':12,'median_dominant_fraction':statistics.median(f['dominant_fraction'] for f in allfaces),'median_equal_neighbor_fraction':statistics.median(f['equal_neighbor_fraction'] for f in allfaces if f['equal_neighbor_fraction'] is not None),'median_isolated_fraction':statistics.median(f['isolated_exact_color_fraction'] for f in allfaces),'by_relation':{}}
    for label in ['up/down','north/south','vertical']:
        vals=[p['delta'] for r in records for p in (r['same_hue_vertical_candidates'] if label=='vertical' else r['same_hue_opposite_face_candidates']) if label=='vertical' or '/'.join(p['faces'])==label]
        summary['by_relation'][label]={'candidates':len(vals),'positive_over_1L':sum(x>1 for x in vals),'negative_below_minus_1L':sum(x< -1 for x in vals),'within_1L':sum(abs(x)<=1 for x in vals),'median_delta_L':statistics.median(vals) if vals else None}
    summary['limitations']='Purposeful 320-species reuse; face-weighted candidate counts, NOT independent species votes; hue bins do not prove common material; internal faces are included; no engine light inferred.'
    write(out/'summary.json',summary);print(json.dumps(summary))


def contacts(a):
    out=Path(a.out); samples=read(out/'manifest.json')['samples'];(out/'contacts').mkdir(exist_ok=True)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
    for start in range(0,len(samples),8):
        cv=Image.new('RGB',(1536,1248),'#dfe6e9');draw=ImageDraw.Draw(cv)
        for j,s in enumerate(samples[start:start+8]):
            source=Image.open(out/'native'/f"{s['species']}-shading.png")
            # Native unlit row: front/side/back, no shaded screenshots substituted.
            strip=source.crop((0,0,768,284))
            x=(j%2)*768;y=(j//2)*312
            cv.paste(strip,(x,y+26));draw.text((x+8,y+3),s['species'],font=font,fill='#1e3545')
        cv.save(out/'contacts'/f'{start//8+1:02}.png')
    print(json.dumps({'contact_pages':math.ceil(len(samples)/8)}))


def verify(a):
    out=Path(a.out);m=read(out/'manifest.json')
    bad=[p for p,h in m['source_sha256'].items() if digest(p)!=h]
    assert not bad,bad
    n=read(out/'native-results.json');assert len(n)==m['count'] and all(r['success'] for r in n)
    assert len({r['species'] for r in n})==m['count']
    print(json.dumps({'unchanged_sources':len(m['source_sha256']),'native_success':len(n)}))


def details(a):
    out=Path(a.out); manifest=read(out/'manifest.json');names=a.species.split(',')
    samples={s['species']:s for s in manifest['samples']};(out/'details').mkdir(exist_ok=True)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15);records=[]
    for name in names:
        s=samples[name]; native=read(out/'surfaces'/f'{name}.json');im=Image.open(s['texture']).convert('RGBA')
        geo=read(s['model'])['minecraft:geometry'][0];rw,rh=geo['description']['texture_width'],geo['description']['texture_height']
        cubes=defaultdict(list)
        for f in native['surfaces']:cubes[f['cube']].append(f)
        def choose(tokens):
            options=[(i,fs) for i,fs in cubes.items() if fs[0]['bone'].lower() in tokens]
            return max(options,key=lambda it:sum(f['area'] for f in it[1])) if options else None
        head=choose({'head','head_rotation','head_angle'})
        body=choose({'torso','body','torso_middle'})
        selected=[]
        for pair in [head,body]:
            if pair and pair[0] not in [x[0] for x in selected]: selected.append(pair)
        if not selected:raise ValueError(name)
        cv=Image.new('RGB',(1024,300+len(selected)*190),'#dfe6e9');draw=ImageDraw.Draw(cv)
        view=Image.open(out/'native'/f'{name}-shading.png');cv.paste(view.crop((0,0,1024,284)),(0,16))
        draw.text((10,0),name+' / raw base texture; no editor light',font=font,fill='#1e3545')
        chosen=[]
        for row,(i,faces) in enumerate(selected):
            for col,key in enumerate(['north','east','south','west','up','down']):
                f=next((f for f in faces if f['face']==key),None)
                if not f:continue
                u,v,u2,v2=f['uv'];u,u2=u*im.width/rw,u2*im.width/rw;v,v2=v*im.height/rh,v2*im.height/rh
                rect=(math.floor(min(u,u2)),math.floor(min(v,v2)),math.ceil(max(u,u2)),math.ceil(max(v,v2)))
                patch=im.crop(rect)
                if u2<u:patch=patch.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                if v2<v:patch=patch.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                if f['rotation']:patch=patch.rotate(-f['rotation'],expand=True)
                scale=max(1,min(150//patch.width,130//patch.height));patch=patch.resize((patch.width*scale,patch.height*scale),Image.Resampling.NEAREST)
                x=col*170+8;y=300+row*190;cv.paste(patch,(x,y),patch)
                draw.text((x,y+134),f"{f['bone']} #{i}"[:23],font=font,fill='#1e3545');draw.text((x,y+155),f"{key} {abs(u2-u):g}x{abs(v2-v):g}",font=font,fill='#1e3545')
                chosen.append({k:f[k] for k in ['cube','bone','face','uv','rotation','normal']})
        cv.save(out/'details'/f'{name}.png');records.append({'species':name,'selected_faces':chosen,'selection':'Largest directly named head and torso cube; not whole material segmentation; UV patches retain local orientation, world normals recorded.'})
    write(out/'detail-selection.json',records);print(json.dumps({'detail_species':len(records)}))


def report(a):
    out=Path(a.out);m=read(out/'manifest.json');summary=read(out/'summary.json');notes=read(out/'visual-notes.json');details=read(out/'detail-selection.json')
    intro=(out/'FINDINGS.md').read_text(encoding='utf-8')
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cobblemon 整体明暗专项 · 320 物种</title><style>body{margin:0;background:#eef2f4;color:#21323d;font:16px system-ui}main{max-width:1180px;margin:auto;padding:24px}section{background:white;padding:20px;margin:20px 0;border-radius:12px}img{max-width:100%;image-rendering:pixelated}pre{white-space:pre-wrap;font:inherit;line-height:1.8}summary{cursor:pointer;padding:12px}a{color:#225e91}p{line-height:1.8}</style><main><h1>320 物种 · 整体明暗与像素过渡专项</h1>'
    page+='<p>复用此前 320 个不同物种，非新增 320 只。原资产及迪莫只读。关闭／开启编辑器面光照各四视角；基础贴图，不合成条件或效果图层，不代表游戏最终外观。</p>'
    page+='<section><pre>'+html.escape(intro)+'</pre></section>'
    page+='<section><h2>24 只重点 UV 对照</h2><p>上方为关闭编辑器光照的正、侧、背、斜视；下方为最大头／躯干块的实际 UV 面。未提取的眼片、毛领、附肢不在这些 UV 小图中。色块方向为局部 UV 方向，不能把图集上下直接当世界上下。</p>'
    for r in details:
        name=r['species'];page+=f'<details><summary>{name} — {html.escape(notes["details"].get(name,""))}</summary><img loading="lazy" src="details/{name}.png"><p><a href="native/{name}-shading.png">查看开／关光照对照</a> · <a href="records/{name}.json">实际面统计与候选比较</a></p></details>'
    page+='</section><section><h2>320 只联系表 · 40 页</h2><p>逐页人工查看，属于整体明暗粗审；长体、展开翅膀和道具主导镜位的物种不能由缩略图宣称像素精审。</p>'
    for i,note in enumerate(notes['pages'],1):page+=f'<details><summary>{i:02} — {html.escape(note)}</summary><img loading="lazy" src="contacts/{i:02}.png"></details>'
    page+='</section><section><h2>全部原生记录</h2>'
    page+=' · '.join(f'<a href="native/{s["species"]}-shading.png">{s["species"]}</a>' for s in m['samples'])
    page+='</section><footer><p>来源：本地 Cobblemon Forge 1.5.2+1.20.1；资产作者为 Cobblemon 项目及其贡献者。未改原资产；模型为绑定姿势，图片是研究用编辑器渲染和 UV 提取。<a href="asset-license.txt">原资产许可</a>，仅作本地非商业研究；公开分发前另核对署名及角色权利。Skill 不捆绑原资产及本报告截图。</p></footer></main></html>'
    (out/'report.html').write_text(page,encoding='utf-8');print(json.dumps({'report_species':m['count'],'detail_species':len(details),'page_notes':len(notes['pages'])}))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['prepare','analyze','contacts','verify','details','report']);ap.add_argument('--out',required=True);ap.add_argument('--manifest',action='append',default=[]);ap.add_argument('--species',default='')
    args=ap.parse_args();globals()[args.mode](args)
