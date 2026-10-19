"""Read-only Cobblemon corpus analysis. Requires Python 3 and Pillow.

Produces derived evidence, never rewrites source assets. Native Blockbench
inspection is a separate stage; this script does not claim visual validation.
"""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
from PIL import Image

STRATA = {
    'quadruped_fur': 'eevee vaporeon jolteon flareon espeon umbreon leafeon glaceon sylveon vulpix ninetales growlithe arcanine shinx luxio luxray absol poochyena mightyena zorua bidoof',
    'biped_body': 'pikachu raichu charmander charmeleon charizard squirtle wartortle blastoise totodile croconaw feraligatr cyndaquil quilava typhlosion torchic combusken blaziken riolu lucario psyduck',
    'plant_organic': 'bulbasaur ivysaur venusaur chikorita bayleef meganium treecko grovyle sceptile turtwig grotle torterra oddish gloom vileplume bellsprout weepinbell victreebel cottonee whimsicott',
    'bird_insect': 'pidgey pidgeotto pidgeot spearow fearow hoothoot noctowl starly staravia staraptor rufflet braviary caterpie metapod butterfree weedle kakuna beedrill scyther scizor zubat golbat',
    'aquatic_elongated': 'magikarp gyarados feebas milotic lapras wooper quagsire ekans arbok dratini dragonair dragonite mudkip marshtomp swampert horsea seadra kingdra tentacool tentacruel poliwag poliwhirl',
    'mineral_ghost': 'geodude graveler golem onix steelix aron lairon aggron magnemite magneton magnezone gastly haunter gengar litwick lampent chandelure solosis duosion reuniclus ditto koffing weezing',
}


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def leaves(obj):
    if isinstance(obj, dict):
        for value in obj.values():
            yield from leaves(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from leaves(value)
    else:
        yield obj


def strings(obj):
    return [v for v in leaves(obj) if isinstance(v, str)]


def analyze_geometry(g):
    bones = g['bones']; names = {b['name'] for b in bones}
    cubes = [c for b in bones for c in b.get('cubes', [])]
    parents = {b['name']: b.get('parent') for b in bones}
    def depth(n):
        seen = set()
        while n in parents and parents[n]:
            if n in seen:
                return -1
            seen.add(n); n = parents[n]
        return len(seen)
    planar = [c for c in cubes if 0 in c['size']]
    return {
        'bones': len(bones), 'cubes': len(cubes), 'planar_cubes': len(planar),
        'integer_size_cubes': sum(all(float(v).is_integer() for v in c['size']) for c in cubes),
        'box_uv_cubes': sum(isinstance(c.get('uv'), list) for c in cubes),
        'inflated_cubes': sum(bool(c.get('inflate')) for c in cubes),
        'inflates': sorted({c.get('inflate', 0) for c in cubes}),
        'mirrored_cubes': sum(bool(c.get('mirror')) for c in cubes),
        'rotated_cubes': sum(any(c.get('rotation', [0, 0, 0])) for c in cubes),
        'rotated_bones': sum(any(b.get('rotation', [0, 0, 0])) for b in bones),
        'depth': max(map(depth, names)), 'missing_parents': sorted({p for p in parents.values() if p and p not in names}),
        'roots': [b['name'] for b in bones if not b.get('parent')],
        'eye_bones': sorted(n for n in names if re.search('eye|lid|pupil|brow', n, re.I)),
        'motion_bones': sorted(n for n in names if re.search('leg|arm|foot|paw|tail|wing|ear|head|torso', n, re.I)),
        'planar_bones': [b['name'] for b in bones if any(0 in c['size'] for c in b.get('cubes', []))],
        'resolution': [g['description']['texture_width'], g['description']['texture_height']],
    }


def texture_stats(p):
    im = Image.open(p).convert('RGBA'); pixels = list(im.get_flattened_data() if hasattr(im, 'get_flattened_data') else im.getdata())
    opaque = [v for v in pixels if v[3]]; counts = collections.Counter(opaque)
    colors = len(counts)
    entropy = -sum((n/len(opaque))*math.log2(n/len(opaque)) for n in counts.values()) if opaque else 0
    # Raw atlas adjacency only: this is NOT a fur/noise or aesthetic score.
    edge = same = 0
    for y in range(im.height):
        for x in range(im.width):
            a = im.getpixel((x, y))
            for nx, ny in ((x+1, y), (x, y+1)):
                if nx < im.width and ny < im.height:
                    b = im.getpixel((nx, ny))
                    if a[3] and b[3]:
                        edge += 1; same += a == b
    return {'size': list(im.size), 'colors_nonzero_alpha': colors,
            'alpha_partial_pixels': sum(0 < v[3] < 255 for v in pixels),
            'occupied_fraction': len(opaque)/len(pixels), 'palette_entropy_bits': entropy,
            'same_color_adjacency_fraction': same/edge if edge else None,
            'top_colors': [{'rgba': list(c), 'pixels': n} for c, n in counts.most_common(12)]}


def analyze_animations(files, bone_names):
    result = []
    for file in files:
        for name, a in read(file).get('animations', {}).items():
            tracks = a.get('bones', {}); expr = []
            for value in strings(tracks):
                try:
                    float(value)
                except ValueError:
                    if value not in ('linear', 'catmullrom', 'step', 'entity'):
                        expr.append(value)
            queries = sorted(set(re.findall(r'\b(?:q|query|v|variable|c|context)\.[A-Za-z_][\w.]*', ' '.join(expr))))
            times = []
            for channels in tracks.values():
                for val in channels.values():
                    if isinstance(val, dict):
                        for key in val:
                            try:
                                times.append(float(key))
                            except ValueError:
                                pass
            result.append({'name': name, 'file': str(file), 'loop': a.get('loop', False),
                           'declared_length': a.get('animation_length'), 'last_key_time': max(times, default=0),
                           'tracked_bones': sorted(tracks), 'missing_bones': sorted(set(tracks)-bone_names),
                           'channels': dict(collections.Counter(ch for b in tracks.values() for ch in b if ch in ('rotation','position','scale'))),
                           'timed_entries': len(times), 'expression_count': len(expr), 'queries': queries,
                           'expression_examples': expr[:4], 'has_effects': any(a.get(x) for x in ('sound_effects','particle_effects','timeline'))})
    return result


def enrich_resolvers(records, root):
    """Read all sibling resolver conditions without claiming runtime merge semantics."""
    for s in records:
        variants=[]
        for rp in sorted(Path(s['resolver']).parent.glob('*.json')):
            data=read(rp);s['source_sha256'][str(rp)]=digest(rp)
            for v in data.get('variations',[]):
                variants.append({'file':str(rp),'order':data.get('order',0),**v})
        s['resolver_context']=variants
        textures=[]
        resources=sorted({v for entry in variants for v in strings(entry.get('layers',[])) if ':textures/' in v and v.endswith('.png')})
        for resource in resources:
            lp=root/'assets'/resource.replace(':','/',1)
            item={'resource':resource,'file':str(lp)}
            if lp.exists():
                item['stats']=texture_stats(lp);s['source_sha256'][str(lp)]=digest(lp)
            else:item['missing']=True
            textures.append(item)
        s['conditional_layer_textures']=textures


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--additional-count', type=int, help='Select this many complete new species, evenly spaced in dex order')
    ap.add_argument('--exclude-manifest', type=Path, action='append', default=[])
    ap.add_argument('--enrich-existing', action='store_true', help='Verify prior hashes, then append resolver condition/layer evidence')
    args = ap.parse_args()
    root = args.root.resolve(); out = args.out.resolve()
    if out == root or root in out.parents:
        raise SystemExit('Output must be outside the read-only source corpus')
    if args.enrich_existing:
        manifest=read(out/'manifest.json')
        for s in manifest['samples']:
            for path,sha in s['source_sha256'].items():
                if digest(Path(path))!=sha:raise SystemExit('Source changed: '+path)
        enrich_resolvers(manifest['samples'],root)
        save(out/'manifest.json',manifest)
        summary=read(out/'summary.json')
        summary['resolver_variations']=sum(len(s['resolver_context']) for s in manifest['samples'])
        summary['species_with_conditional_layers']=sum(any(v.get('aspects') and v.get('layers') for v in s['resolver_context']) for s in manifest['samples'])
        summary['conditional_layer_pngs']=len({t['file'] for s in manifest['samples'] for t in s['conditional_layer_textures'] if not t.get('missing')})
        summary['source_files']=len({p for s in manifest['samples'] for p in s['source_sha256']})
        save(out/'summary.json',summary);print(json.dumps({k:summary[k] for k in ['resolver_variations','species_with_conditional_layers','conditional_layer_pngs','source_files']}));return
    if args.verify:
        manifest = read(out/'manifest.json'); changed=[]
        for s in manifest['samples']:
            for path, sha in s['source_sha256'].items():
                if digest(Path(path)) != sha: changed.append(path)
        if changed: raise SystemExit('Source changed: '+repr(changed))
        print('PASS: all selected model, texture, animation and resolver source hashes unchanged'); return
    model_root=root/'assets/cobblemon/bedrock/pokemon/models'; anim_root=model_root.parent/'animations'; resolver_root=model_root.parent/'resolvers'
    models={p.name.rsplit('.json',1)[0]:p for p in model_root.rglob('*.geo.json')}
    dirs={p.name.split('_',1)[1]:p for p in model_root.iterdir() if p.is_dir() and '_' in p.name}
    excluded={s['species'] for p in args.exclude_manifest for s in read(p)['samples']}
    selection_groups=STRATA
    if args.additional_count:
        selection_groups={'dex_spread': ' '.join(sorted((s for s in dirs if s not in excluded),key=lambda s:dirs[s].name))}
    records=[]; missing=[]; license_files={model_root/'license'}
    for category, selection in selection_groups.items():
        for species in selection.split():
            if species in excluded:continue
            if species not in dirs: missing.append([species,'model directory']); continue
            folder=dirs[species].name
            resolvers=sorted((resolver_root/folder).glob('*.json'))
            base=None; resolver=None
            for rp in sorted(resolvers,key=lambda p:read(p).get('order',0)):
                for v in read(rp).get('variations',[]):
                    if v.get('aspects') == [] and v.get('model') and isinstance(v.get('texture'),str):
                        base=v;resolver=rp;break
                if base:break
            if not base:missing.append([species,'base resolver']);continue
            mp=models.get(base['model'].split(':')[-1]);tp=root/'assets'/base['texture'].replace(':','/',1)
            af=sorted((anim_root/folder).glob('*.json'))
            if not mp or not tp.exists() or not af:missing.append([species,'model/texture/animations']);continue
            g=read(mp)['minecraft:geometry'][0]; bn={b['name'] for b in g['bones']}; anim=analyze_animations(af,bn)
            if not anim:missing.append([species,'empty animation library']);continue
            for clip in anim:
                clip['base_name_match']=clip['name'].startswith('animation.'+species+'.')
                clip['resolved_model_name_match']=clip['name'].startswith('animation.'+base['model'].split(':')[-1].removesuffix('.geo')+'.')
            geom=analyze_geometry(g);tex=texture_stats(tp)
            layers=base.get('layers',[]);files=[mp,tp,resolver]+af
            layer_textures=[]
            for resource in sorted(set(v for v in strings(layers) if ':textures/' in v and v.endswith('.png'))):
                lp=root/'assets'/resource.replace(':','/',1)
                if lp.exists():
                    files.append(lp);layer_textures.append({'resource':resource,'file':str(lp),'stats':texture_stats(lp)})
                else:
                    layer_textures.append({'resource':resource,'file':str(lp),'missing':True})
            ownlicense=dirs[species]/'license'
            if ownlicense.exists():license_files.add(ownlicense)
            r={'species':species,'dex':int(folder.split('_')[0]),'stratum':category,'folder':folder,
               'model':str(mp),'texture':str(tp),'animation_files':list(map(str,af)), 'resolver':str(resolver),
               'poser':base.get('poser'),'model_resource':base['model'],'geometry_identifier':g['description']['identifier'],'layers':layers,'layer_textures':layer_textures,'model_stats':geom,'texture_stats':tex,
               'texture_matches_resolution':tex['size']==geom['resolution'],'animations':anim,
               'source_sha256':{str(p):digest(p) for p in files},'visual_status':'pending_native'}
            records.append(r)
    eligible_count=len(records)
    if args.additional_count:
        count=args.additional_count
        if count<2 or count>len(records):raise SystemExit('Additional count must be 2..'+str(len(records)))
        records=[records[round(i*(len(records)-1)/(count-1))] for i in range(count)]
        for r in records:r['stratum']='dex_%04d_%04d'%(((r['dex']-1)//100)*100+1,((r['dex']-1)//100+1)*100)
        license_files={model_root/'license'}|{dirs[r['species']]/'license' for r in records if (dirs[r['species']]/'license').exists()}
    if len(records)<100: raise SystemExit('Fewer than 100 complete unique species: '+str(len(records))+' missing '+repr(missing))
    assert len({r['species'] for r in records})==len(records)
    selection_method='Deterministic evenly spaced dex-order sample from complete eligible species, excluding prior manifests; not random or anatomical strata' if args.additional_count else 'purposeful stratified sample, not random or all-species inference'
    save(out/'manifest.json',{'version':'Cobblemon 1.5.2+1.20.1','root':str(root),'count':len(records),'selection':selection_method,'eligible_count':eligible_count,'excluded_species':sorted(excluded),'omissions':missing,'samples':records})
    metrics={}
    for key in ['bones','cubes','planar_cubes','integer_size_cubes','box_uv_cubes','inflated_cubes','rotated_cubes']:
        vals=[r['model_stats'][key] for r in records];metrics[key]={'sum':sum(vals),'median':statistics.median(vals),'min':min(vals),'max':max(vals)}
    animations=[a for r in records for a in r['animations']]
    summary={'species':len(records),'strata':dict(collections.Counter(r['stratum'] for r in records)),
             'model_metrics':metrics,'texture_sizes':dict(collections.Counter('x'.join(map(str,r['texture_stats']['size'])) for r in records)),
             'texture_color_median':statistics.median(r['texture_stats']['colors_nonzero_alpha'] for r in records),
             'base_textures_with_partial_alpha':sum(r['texture_stats']['alpha_partial_pixels']>0 for r in records),
             'species_with_base_layers':sum(bool(r['layers']) for r in records),'animation_clips':len(animations),
             'clips_with_expressions':sum(a['expression_count']>0 for a in animations),
             'clips_without_declared_length':sum(a['declared_length'] is None for a in animations),
             'clips_with_missing_bones':sum(bool(a['missing_bones']) for a in animations),
             'base_named_clips':sum(a['base_name_match'] for a in animations),
             'base_named_clips_with_missing_bones':sum(a['base_name_match'] and bool(a['missing_bones']) for a in animations),
             'resolved_model_named_clips':sum(a['resolved_model_name_match'] for a in animations),
             'resolved_model_named_clips_with_missing_bones':sum(a['resolved_model_name_match'] and bool(a['missing_bones']) for a in animations),
             'query_counts':dict(collections.Counter(q for a in animations for q in a['queries'])),'omissions':missing}
    save(out/'summary.json',summary)
    licenses={};(out/'licenses').mkdir(parents=True,exist_ok=True)
    for lp in sorted(license_files):
        sha=digest(lp);name='asset-license-'+sha[:12]+'.txt'
        if sha not in licenses:(out/'licenses'/name).write_bytes(lp.read_bytes());licenses[sha]={'file':name,'source_paths':[]}
        licenses[sha]['source_paths'].append(str(lp))
    save(out/'licenses/index.json',list(licenses.values()))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
