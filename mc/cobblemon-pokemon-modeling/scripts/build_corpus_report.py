"""Assemble local derived visual evidence and a searchable corpus report.
Run after analyze_corpus.py and native Blockbench capture. Does not edit assets.
"""
import argparse
import html
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);parser.add_argument('--contacts-only',action='store_true');args=parser.parse_args()
    out=args.output.resolve();manifest=read(out/'manifest.json');native=read(out/'native-results.json');results={r['species']:r for r in native}
    notes=read(out/'visual-notes.json') if (out/'visual-notes.json').exists() else {}
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
    contactdir=out/'contacts';contactdir.mkdir(exist_ok=True)
    complete=[s for s in manifest['samples'] if results.get(s['species'],{}).get('success')]
    for start in range(0,len(complete),10):
        group=complete[start:start+10]
        sheet=Image.new('RGB',(1200,1750),'#dbe5eb');draw=ImageDraw.Draw(sheet)
        for j,s in enumerate(group):
            x=(j%2)*600;y=(j//2)*350;name=s['species'];base=out/'native'
            view=Image.open(base/(name+'-views.png')).convert('RGB');texture=Image.open(base/(name+'-texture.png')).convert('RGB');motion=Image.open(base/(name+'-motion.png')).convert('RGB')
            sheet.paste(view.crop((768,0,1024,256)).resize((190,190),Image.Resampling.NEAREST),(x,y+25))
            sheet.paste(view.crop((0,0,256,256)).resize((190,190),Image.Resampling.NEAREST),(x+195,y+25))
            sheet.paste(texture.resize((190,190),Image.Resampling.NEAREST),(x+390,y+25))
            for k,frame in enumerate([0,3,7,11]):
                fx=frame%8*192;fy=frame//8*192
                sheet.paste(motion.crop((fx,fy,fx+192,fy+192)).resize((130,130),Image.Resampling.NEAREST),(x+k*145,y+218))
            draw.text((x+5,y+3),f"{start+j+1:03d} {name} / {s['model_stats']['cubes']} cubes / {s['texture_stats']['colors_nonzero_alpha']} colors",fill='#172b3a',font=font)
        sheet.save(contactdir/f'overview-{start//10+1:02d}.png')
    if args.contacts_only:
        print('Contact sheets for',len(complete),'successful native samples');return
    cards=[]
    for s in manifest['samples']:
        n=s['species'];r=results.get(n,{});g=s['model_stats'];t=s['texture_stats'];base=[a for a in s['animations'] if a.get('resolved_model_name_match',False)] or [a for a in s['animations'] if a['base_name_match']]
        scope={'species':n,'model':s['model'],'texture':s['texture'],'animation_files':s['animation_files'],'resolver':s['resolver'],'stats':g,'texture_stats':t,'animations':s['animations'],'native':r,'visual_notes':notes.get(n,{}),'review_scope':'Contact-sheet visual review plus file analysis; selected clips only, not full library playback' if notes.get(n) else 'File analysis; manual visual notes pending'}
        (out/'records').mkdir(exist_ok=True)
        scope.update({k:s[k] for k in ['model_resource','geometry_identifier','resolver_context','conditional_layer_textures'] if k in s})
        (out/'records'/f'{n}.json').write_text(json.dumps(scope,ensure_ascii=False,indent=2),encoding='utf-8')
        observations=[f"{g['cubes']} cubes，{g['planar_cubes']} 个零厚度，{g['bones']} bones，层级深度 {g['depth']}。",f"基础 PNG {t['size'][0]}×{t['size'][1]}，{t['colors_nonzero_alpha']} 个非透明 RGBA 色值；图层 {len(s['layers'])} 个。",f"目录内 {len(s['animations'])} 段动画，其中所选模型命名空间 {len(base)} 段；{sum(a['expression_count']>0 for a in base)} 段含表达式。"]
        warning=[]
        if s['layers']:warning.append('图层预览是首帧普通 source-over 合成，不是发光/半透明运行时验证。')
        if any(v.get('aspects') and v.get('layers') for v in s.get('resolver_context',[])):warning.append('存在条件图层；下图仅为无额外 aspect 的基础分支，可能缺少花色等可见部件，不代表默认游戏外观。')
        if any(a['missing_bones'] for a in base):warning.append('所选模型或共享物种命名空间存在未匹配骨骼引用；见记录，不能直接认定运行时故障。')
        note=notes.get(n,{})
        card=f'<article id="{n}" data-search="{n} {s["stratum"]}"><h2>{s["dex"]:04d} · {n}</h2><p class="tag">{s["stratum"]}</p><p>'+html.escape(' '.join(observations))+'</p>'
        card+=f'<p>以下为绑定姿势四视角，并非运行时待机姿势。</p><img loading="lazy" class="views" src="native/{n}-views.png" alt="{n} 绑定姿势四视角"><details><summary>基础图集、原始路径与分析记录</summary><img loading="lazy" class="tex" src="native/{n}-texture.png"><p><a href="records/{n}.json">逐只分析 JSON</a></p><code>{html.escape(s["model"])}</code></details>'
        if note:card+='<p class="note">'+html.escape('；'.join(note.values()))+'</p>'
        supplement=out/'supplemental'/f'{n}_flower_red-views.png'
        if supplement.exists():card+=f'<details><summary>显式 flower-red 图层对照（不是默认状态断言）</summary><img loading="lazy" class="views" src="supplemental/{n}_flower_red-views.png"></details>'
        wide=out/'supplemental'/f'{n}_wide-motion.png'
        if wide.exists():card+=f'<details><summary>动作宽镜位补充：检查道具出画面</summary><img loading="lazy" class="views" src="supplemental/{n}_wide-motion.png"></details>'
        card+='<div class="motions">'
        for m in r.get('motions',[]):
            card+=f'<div><h3>{html.escape(m["name"])}</h3><canvas width="192" height="192" data-image="native/{n}-{m["label"]}.png" data-duration="{m["seconds"]}"></canvas><p>观察窗 {m["seconds"]} s · 24 帧<br>{html.escape(m["window_source"])}</p></div>'
        card+='</div><p class="warn">'+html.escape(' '.join(warning))+'</p></article>';cards.append(card)
    licenses=read(out/'licenses/index.json');license_links=' '.join(f'<a href="licenses/{v["file"]}">原资产许可 {i+1}</a>' for i,v in enumerate(licenses))
    summary=read(out/'summary.json')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cobblemon @COUNT@ 样本蒸馏</title><style>
body{margin:0;background:#eef2f4;color:#213443;font:15px/1.7 system-ui,sans-serif}main{max-width:1120px;margin:auto;padding:24px}header,article{background:white;padding:24px;margin-bottom:20px;border-radius:14px}h1{margin:0}h2{margin:0 0 8px}a{color:#165fa5}input{padding:12px;width:360px;max-width:90%;border:1px solid #bcc8d1;border-radius:7px}button{padding:8px 16px}.toolbar{position:sticky;top:0;background:#eef2f4;padding:12px;z-index:2}.views{width:100%;image-rendering:pixelated}.tex{width:320px;max-width:100%;image-rendering:pixelated}.motions{display:flex;gap:28px;flex-wrap:wrap}canvas{width:240px;height:240px;image-rendering:pixelated;background:#dbe5eb}.motions h3{font-size:13px}code{display:block;overflow-wrap:anywhere;font-size:11px}.warn{color:#866230}.note{border-left:3px solid #508aac;padding-left:12px}.tag{font-size:12px;color:#617783}summary{cursor:pointer}details{margin:12px 0}[hidden]{display:none}</style><main>
<header><h1>Cobblemon · @COUNT@ 只模型／材质／动作分析</h1><p>来源：本地 Cobblemon Forge 1.5.2+1.20.1。选样方法：@SELECTION@。不是随机样本，也不是对全部物种的完备结论。</p>
<p>文件分析 @COUNT@ 只；原生绑定姿势四视角检查成功 @NATIVE@ 只；已有人工联系表笔记 @NOTES@ 只。解析 @CLIPS@ 段目录动画；每只设置待机优先槽位与移动优先槽位（缺少对应定义时使用替代动作），共 @SLOTS@ 个槽位、@UNIQUE@ 段不同动画，并非全部动画逐帧目检。每槽位 25 个数值采样时刻及 24 个渲染帧。观察窗优先使用正数声明时长，其次最后关键帧时间，二者都无才取 2 秒；观察窗不必等于真实循环周期。</p>
<p>移动优先槽位中 @LOCOMOTION@ 个选中了 walk/swim/fly/flight/float 命名动作，其余为眨眼、叫声、姿态等替代观察；这不证明游戏中缺少移动。模型形态及命名空间先按 resolver 关联，再检查共享动画与 poser，不能把绑定姿势当最终游戏姿势。</p>
<p>本报告不包含游戏运行验收、poser 状态混合、粒子或声音测试。下方播放器按观察窗回放，窗口末端跳转不一定是原动画接缝。</p><p><a href="summary.json">统计摘要</a> · <a href="manifest.json">完整来源与 SHA-256 清单</a> · <a href="FINDINGS.md">蒸馏结论与限制</a></p>
<p>原始美术资产：Cobblemon 及其贡献者；宝可梦相关权利归各权利人。此处为本地研究用的渲染与分析，未修改原文件，不向 Skill 捆绑原资产，不代表官方认可。</p>'''+license_links+'''</header><div class="toolbar"><input id="search" placeholder="搜索物种英文名或类型"><button id="play">播放可见动画</button><button id="step">全局下一帧</button><span id="count"></span></div>'''+''.join(cards)+'''</main><script>
const cards=[...document.querySelectorAll('article')],canvases=[...document.querySelectorAll('canvas')];let playing=false,clock=0,previous=performance.now();const visible=new Set();const watcher=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){visible.add(e.target);ensureImage(e.target);}else visible.delete(e.target)}));
function ensureImage(cv){if(cv.pic)return;const im=new Image();cv.pic=im;im.onload=()=>paint(cv,clock);im.src=cv.dataset.image;}
for(const cv of canvases)watcher.observe(cv);
function paint(cv,t){const im=cv.pic;if(!im||!im.complete||!im.naturalWidth)return;const n=Math.floor(t/Number(cv.dataset.duration)*24)%24,c=cv.getContext('2d');c.imageSmoothingEnabled=false;c.clearRect(0,0,192,192);c.drawImage(im,n%8*192,Math.floor(n/8)*192,192,192,0,0,192,192);cv.dataset.frame=n;}
document.getElementById('play').onclick=()=>{playing=!playing;document.getElementById('play').textContent=playing?'暂停':'播放可见动画';};document.getElementById('step').onclick=()=>{playing=false;document.getElementById('play').textContent='播放可见动画';visible.forEach(cv=>paint(cv,((Number(cv.dataset.frame||0)+1)%24+.001)*Number(cv.dataset.duration)/24));};
function tick(now){if(playing){clock+=Math.min(.1,(now-previous)/1000);visible.forEach(cv=>paint(cv,clock));}previous=now;requestAnimationFrame(tick)}requestAnimationFrame(tick);
function filter(){const q=document.getElementById('search').value.toLowerCase();cards.forEach(c=>c.hidden=!c.dataset.search.includes(q));document.getElementById('count').textContent=cards.filter(c=>!c.hidden).length+' / '+cards.length;};document.getElementById('search').oninput=filter;filter();document.body.dataset.ready='true';
</script></html>'''
    replacements={'@COUNT@':len(manifest['samples']),'@SELECTION@':html.escape(manifest['selection']),'@NATIVE@':len(complete),'@NOTES@':sum(bool(notes.get(s['species'])) for s in manifest['samples']),'@CLIPS@':summary['animation_clips'],'@SLOTS@':sum(len(r.get('motions',[])) for r in native if r.get('success')),'@UNIQUE@':len({(r['species'],a['name']) for r in native if r.get('success') for a in r.get('motions',[])})}
    replacements['@LOCOMOTION@']=sum(a['label']=='motion' and any(word in a['name'].split('.')[-1] for word in ('walk','swim','fly','flight','float')) for r in native if r.get('success') for a in r.get('motions',[]))
    for marker,value in replacements.items():page=page.replace(marker,str(value))
    (out/'report.html').write_text(page,encoding='utf-8')
    print(json.dumps({'records':len(manifest['samples']),'native_success':len(complete),'notes':len(notes),'report':str(out/'report.html')},ensure_ascii=False))


if __name__=='__main__':main()
