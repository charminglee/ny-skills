"""Read-only whole-corpus index. Generated evidence is not visual approval."""
import argparse, collections, hashlib, json, math, re, shutil, struct
from pathlib import Path
from PIL import Image

def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def strings(v):
    if isinstance(v,str): yield v
    elif isinstance(v,dict):
        for x in v.values(): yield from strings(x)
    elif isinstance(v,list):
        for x in v: yield from strings(x)
def cp_utf8(p):
    data=p.read_bytes(); n=struct.unpack_from('>H',data,8)[0]; at=10; i=1; out=[]
    while i<n:
        tag=data[at];at+=1
        if tag==1:
            size=struct.unpack_from('>H',data,at)[0];at+=2;out.append(data[at:at+size].decode('utf-8','replace'));at+=size
        elif tag in (3,4,9,10,11,12,17,18):at+=4
        elif tag in (5,6):at+=8;i+=1
        elif tag in (7,8,16,19,20):at+=2
        elif tag==15:at+=3
        else:raise ValueError(f'constant tag {tag}')
        i+=1
    return out

def prepare(root,out):
    root=root.resolve();out.mkdir(parents=True,exist_ok=True)
    asset=root/'assets/cobblemon'; bed=asset/'bedrock/pokemon'
    sources={}
    def record(p):
        rel=p.relative_to(root).as_posix()
        sources[rel]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
        return str(p)
    model_files=sorted((bed/'models').rglob('*.json'))
    texture_files=sorted((asset/'textures/pokemon').rglob('*.png'))
    model_names={p.name.removesuffix('.json'):p for p in model_files}
    issues=[];variants=[];species_base={}
    resolver_data=[(p,read(p)) for p in sorted((bed/'resolvers').rglob('*.json'))]
    for p,d in sorted(resolver_data,key=lambda x:x[1].get('order',0)):
        for v in d.get('variations',[]):
            if not v.get('aspects'):species_base[d.get('species')]={**species_base.get(d.get('species'),{}),**v}
    for p,d in resolver_data:
        record(p);base=species_base.get(d.get('species'),{}).copy()
        for i,v in enumerate(d.get('variations',[])):
            if not v.get('aspects'):base={**base,**v}
            effective={**base,**v}
            name=str(effective.get('model','')).split(':')[-1]
            mp=model_names.get(name);tr=effective.get('texture');tp=asset/tr.split(':',1)[-1] if isinstance(tr,str) else None
            layers=effective.get('layers',[])
            layer_files=[]
            for layer in layers:
                tex=layer.get('texture');rs=[tex] if isinstance(tex,str) else tex.get('frames',[]) if isinstance(tex,dict) else []
                for resource in rs:
                    lp=asset/resource.split(':',1)[-1]
                    layer_files.append({'resource':resource,'file':str(lp),'exists':lp.exists(),'emissive':bool(layer.get('emissive')),'translucent':bool(layer.get('translucent')),'layer':layer.get('name')})
            entry={'resolver':str(p),'species':d.get('species'),'order':d.get('order'), 'index':i,'aspects':v.get('aspects',[]),'explicit_fields':sorted(v),'model':str(mp) if mp else None,'model_resource':name,'texture':str(tp) if tp else None,'poser':effective.get('poser'),'layers':layers,'layer_files':layer_files,'semantics':'branch overrides unconditional same-species fields in order; mutually combined conditional branches and runtime matcher not asserted'}
            variants.append(entry)
            if name and not mp:issues.append({'type':'missing_model_reference','resolver':str(p),'resource':name})
            if tp and not tp.exists():issues.append({'type':'missing_texture_reference','resolver':str(p),'resource':tr})
    textures=[]
    for p in texture_files:
        record(p)
        with Image.open(p) as im:
            rgba=im.convert('RGBA'); colors=collections.Counter(rgba.getdata());opaque={k:v for k,v in colors.items() if k[3]}
            textures.append({'file':str(p),'size':list(im.size),'nonzero_alpha_colors':len(opaque),'alpha_values':sorted({k[3] for k in colors}),'visible_pixels':sum(opaque.values()),'scope':'whole atlas; includes unused pixels'})
    animations=[]
    for p in sorted((bed/'animations').rglob('*.json')):
        record(p)
        for name,a in read(p).get('animations',{}).items():
            texts=list(strings(a));expr=[s for s in texts if re.search(r'[A-Za-z_]',s) and s not in ('linear','catmullrom','hold_on_last_frame')]
            queries=sorted(set(re.findall(r'\b(?:q|query|v|variable|t|temp)\.[a-zA-Z_][\w.]*',' '.join(expr))))
            times=[]
            for channels in a.get('bones',{}).values():
                for v in channels.values():
                    if isinstance(v,dict):
                        for t in v:
                            try:times.append(float(t))
                            except ValueError:pass
            unsupported=[q for q in queries if q.lower() not in ('q.anim_time','query.anim_time')]
            duration=a.get('animation_length');window=duration if isinstance(duration,(float,int)) and duration>0 else max(times,default=0) or 2
            animations.append({'name':name,'file':str(p),'folder':p.parent.name,'bones':list(a.get('bones',{})),'loop':a.get('loop',False),'declared_length':duration,'last_key_time':max(times,default=0),'window':window,'window_source':'declared' if duration else 'last-key-or-observation-NOT-proven-period','queries':queries,'unresolved_variables':unsupported,'expression_count':len(expr),'effects':sorted(set(a)-{'bones','loop','animation_length'}),'native_candidate':not unsupported})
    by_folder=collections.defaultdict(list)
    for a in animations:by_folder[a['folder']].append(a)
    by_model=collections.defaultdict(list)
    for v in variants:
        if v['model']:by_model[v['model']].append(v)
    records=[]
    for p in model_files:
        record(p);d=read(p);g=d['minecraft:geometry'][0];bones=g.get('bones',[]);names={b['name'] for b in bones};cubes=[c for b in bones for c in b.get('cubes',[])]
        species=p.parent.name.split('_',1)[-1];modelname=p.name.removesuffix('.geo.json')
        vv=by_model[str(p)];valid=[v for v in vv if v['texture'] and Path(v['texture']).exists()]
        valid.sort(key=lambda v:(any('shiny' in x for x in v['aspects']),len(v['aspects']),v['index']))
        selected=valid[0] if valid else None
        possible=by_folder[p.parent.name];own=[a for a in possible if a['name'].startswith('animation.'+modelname+'.')];shared=[a for a in possible if a['name'].startswith('animation.'+species+'.')]
        chosen=own or shared
        for a in chosen:a['missing_bones_'+modelname]=sorted(set(a['bones'])-names)
        record_data={'id':p.parent.name+'__'+modelname,'species':species,'modelname':modelname,'model':str(p),'description':g['description'],'texture':selected['texture'] if selected else None,'selected_variation':selected,'variation_count':len(vv),'variants':vv,'bones':len(bones),'cubes':len(cubes),'planes':sum(0 in c.get('size',[]) for c in cubes),'rotated_cubes':sum(any(c.get('rotation',[])) for c in cubes),'inflated_cubes':sum(bool(c.get('inflate')) for c in cubes),'box_uv':sum(isinstance(c.get('uv'),list) for c in cubes),'fractional_sizes':sum(any(x%1 for x in c.get('size',[])) for c in cubes),'parent_errors':[b['name'] for b in bones if b.get('parent') and b['parent'] not in names],'animations':chosen,'namespace':modelname if own else species if shared else None,'source_hash':sources[p.relative_to(root).as_posix()]['sha256'],'visual_status':'pending'}
        records.append(record_data)
    classes=[]
    class_root=root/'com/cobblemon/mod/common/client/render/models/blockbench'
    for p in sorted(class_root.rglob('*.class')):
        if 'pokemon' not in str(p).lower() and 'animation' not in str(p).lower() and 'poser' not in str(p).lower():continue
        vals=cp_utf8(p);record(p)
        references=[s for s in vals if re.search(r'Biped|Quadruped|WalkAnimation|Wing|look|blink|ground_walk|ground_idle|registerPose|PoseType|swim|flying|bedrockStateful|bedrockStateless',s,re.I) and len(s)<350]
        classes.append({'file':str(p),'name':p.stem,'references':references,'evidence':'constant pool references only; NOT control-flow reconstruction'})
    out.joinpath('licenses').mkdir(exist_ok=True)
    shutil.copy2(bed/'models/license',out/'licenses/cobblemon-assets-license.txt')
    authors={}
    for p in sorted((bed/'models').rglob('license')):
        rel=record(p);authors[p.parent.name]=p.read_text(encoding='utf-8',errors='replace')
    write(out/'attribution.json',authors)
    summary={'models':len(records),'species_folders':len({r['species'] for r in records}),'textures':len(textures),'animation_files':len({a['file'] for a in animations}),'animation_clips':len(animations),'clips_with_external_variables':sum(bool(a['unresolved_variables']) for a in animations),'resolvers':len({v['resolver'] for v in variants}),'variations':len(variants),'model_bindings_found':sum(bool(r['texture']) for r in records),'bones':sum(r['bones'] for r in records),'cubes':sum(r['cubes'] for r in records),'planes':sum(r['planes'] for r in records),'code_class_records':len(classes),'issues':len(issues)}
    write(out/'manifest.json',{'root':str(root),'version':'Cobblemon-forge-1.5.2+1.20.1','summary':summary,'models':records})
    write(out/'animations.json',animations);write(out/'textures.json',textures);write(out/'variations.json',variants);write(out/'code-index.json',classes);write(out/'source-hashes.json',sources);write(out/'issues.json',issues);write(out/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False))

def verify(root,out):
    src=read(out/'source-hashes.json');bad=[]
    for rel,r in src.items():
        p=root/rel
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:bad.append(rel)
    print(json.dumps({'checked':len(src),'changed':bad}));assert not bad

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','verify']);ap.add_argument('--root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ns=ap.parse_args();globals()[ns.mode](ns.root,ns.out)
