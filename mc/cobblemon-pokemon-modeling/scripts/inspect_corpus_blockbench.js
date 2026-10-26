/* Run in Blockbench MCP risky_eval after setting window.CB_STUDY_OUTPUT.
 * cbStudy.run(start,count) is asynchronous and checkpoints after each sample.
 * Read-only originals; isolated preview projects are closed without saving.
 */
(()=>{
const fs=require('fs'),path=require('path');
const dir=window.CB_STUDY_OUTPUT;if(!dir)throw Error('Set CB_STUDY_OUTPUT');
const manifest=JSON.parse(fs.readFileSync(path.join(dir,'manifest.json'),'utf8'));
const original=Project.uuid,initial=ModelProject.all.map(p=>p.uuid);
fs.mkdirSync(path.join(dir,'native'),{recursive:true});fs.mkdirSync(path.join(dir,'backup'),{recursive:true});
const snapshot=path.join(dir,'backup','active-project-before.bbmodel');if(!fs.existsSync(snapshot))fs.writeFileSync(snapshot,Codecs.project.compile());
const recordPath=path.join(dir,'native-results.json');
window.cbStudy={dir,manifest,original,initial,results:fs.existsSync(recordPath)?JSON.parse(fs.readFileSync(recordPath,'utf8')):[],status:{running:false}};
const c=cbStudy;
c.save=(canvas,name)=>fs.writeFileSync(path.join(dir,'native',name),Buffer.from(canvas.toDataURL().split(',')[1],'base64'));
c.image=p=>new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('Image load '+p));im.src='data:image/png;base64,'+fs.readFileSync(p).toString('base64');});
c.bounds=()=>{Project.model_3d.updateMatrixWorld(true);const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];for(const cube of Cube.all){const a=cube.mesh.geometry.attributes.position;for(let i=0;i<a.count;i++){const v=new THREE.Vector3().fromBufferAttribute(a,i).applyMatrix4(cube.mesh.matrixWorld);[v.x,v.y,v.z].forEach((n,j)=>{min[j]=Math.min(min[j],n);max[j]=Math.max(max[j],n);});}}return{min,max};};
c.render=(center,span,view,size=256)=>{
const dirs={front:[0,0,-1],side:[1,0,0],back:[0,0,1],threequarter:[.65,.28,-1]};const dv=new THREE.Vector3(...dirs[view]).normalize().multiplyScalar(span*3);
const camera=new THREE.OrthographicCamera(-span/2,span/2,span/2,-span/2,.01,span*10+100);camera.position.fromArray(center).add(dv);camera.lookAt(new THREE.Vector3(...center));camera.updateMatrixWorld(true);
const r=Preview.selected.renderer,sz=new THREE.Vector2();r.getSize(sz);const ratio=r.getPixelRatio(),bg=Canvas.scene.background,hidden=[];
Canvas.scene.traverse(o=>{if(o.visible&&(o.type==='GridHelper'||o===Canvas.ground||o.name==='grid'||o.name==='grid_group')){hidden.push(o);o.visible=false;}});
r.setPixelRatio(1);r.setSize(size,size,false);Canvas.scene.background=new THREE.Color('#dbe5eb');r.render(Canvas.scene,camera);
const cv=document.createElement('canvas');cv.width=cv.height=size;cv.getContext('2d').drawImage(r.domElement,0,0);Canvas.scene.background=bg;hidden.forEach(o=>o.visible=true);r.setPixelRatio(ratio);r.setSize(sz.x,sz.y,false);return cv;
};
c.pose=(a,t)=>{Modes.options.animate.select();Timeline.pause();Animation.all.forEach(x=>x.playing=false);a.select();a.playing=true;Timeline.setTime(t);Animator.preview();Project.model_3d.updateMatrixWorld(true);};
c.rest=()=>{Timeline.pause();Animation.all.forEach(a=>a.playing=false);Modes.options.edit.select();Canvas.updateAll();Canvas.updateAllBones();Animator.showDefaultPose();Project.model_3d.updateMatrixWorld(true);};
c.inspect=async s=>{
newProject(Formats.bedrock);const audit=Project;audit.name='CORPUS_READONLY_'+s.species;
try{
Codecs.bedrock.parse(JSON.parse(fs.readFileSync(s.model,'utf8')));audit.save_path='';audit.export_path='';
if(Cube.all.length!==s.model_stats.cubes||Group.all.length!==s.model_stats.bones)throw Error('Import count mismatch');
const im=await c.image(s.texture),canvas=document.createElement('canvas');canvas.width=im.width;canvas.height=im.height;const cx=canvas.getContext('2d');cx.drawImage(im,0,0);
const layerPreview=[];
for(const layer of s.layers){const resource=typeof layer.texture==='string'?layer.texture:layer.texture?.frames?.[0];const file=s.layer_textures?.find(t=>t.resource===resource);if(file&&!file.missing){const li=await c.image(file.file);cx.drawImage(li,0,0);layerPreview.push({name:layer.name,resource,emissive:!!layer.emissive,translucent:!!layer.translucent,preview:'source-over static first frame; not runtime shader'});}}
const texture=new Texture({name:s.species+'_study.png'}).fromDataURL(canvas.toDataURL()).add(false);
await new Promise(resolve=>texture.load(resolve));
texture.path='';texture.saved=true;
for(const cube of Cube.all)for(const face of Object.values(cube.faces))face.texture=texture.uuid;
for(const file of s.animation_files)AnimationCodec.codecs.bedrock.loadFile({name:path.basename(file),path:'',json:JSON.parse(fs.readFileSync(file,'utf8'))});
c.rest();const bounds=c.bounds(),center=bounds.min.map((v,i)=>(v+bounds.max[i])/2),dim=bounds.max.map((v,i)=>v-bounds.min[i]),span=Math.max(dim[1],Math.hypot(dim[0],dim[2]))*1.22;
const views=document.createElement('canvas');views.width=1024;views.height=280;const vx=views.getContext('2d');vx.fillStyle='#dbe5eb';vx.fillRect(0,0,1024,280);
['front','side','back','threequarter'].forEach((v,i)=>{vx.drawImage(c.render(center,span,v),256*i,0);vx.fillStyle='#243746';vx.font='14px sans-serif';vx.fillText(s.species+' / '+v,256*i+8,274);});c.save(views,s.species+'-views.png');
const texview=document.createElement('canvas');texview.width=texview.height=320;const tx=texview.getContext('2d');tx.fillStyle='#8d99a3';tx.fillRect(0,0,320,320);tx.imageSmoothingEnabled=false;const ratio=Math.min(288/im.width,288/im.height);tx.drawImage(im,16,16,im.width*ratio,im.height*ratio);tx.fillStyle='white';tx.font='12px sans-serif';tx.fillText(s.species+' base '+im.width+' x '+im.height,8,312);c.save(texview,s.species+'-texture.png');
const imported=Animation.all.slice(),modelName=(s.model_resource?.split(':').pop()||path.basename(s.model,'.json')).replace(/\.geo$/,''),modelClips=imported.filter(a=>a.name.startsWith('animation.'+modelName+'.')),base=imported.filter(a=>a.name.startsWith('animation.'+s.species+'.')),all=modelClips.length?modelClips:base.length?base:imported,idle=all.find(a=>/ground_idle$/.test(a.name))||all.find(a=>/idle$/.test(a.name))||all[0],move=all.find(a=>/ground_walk$/.test(a.name))||all.find(a=>/walk|swim|fly|flight|float/.test(a.name)&&!a.name.endsWith('idle'))||all.find(a=>a!==idle)||idle;
const motions=[];
for(const [label,a] of [['idle',idle],['motion',move]]){
const source=s.animations.find(x=>x.name===a.name),seconds=source.declared_length>0?source.declared_length:source.last_key_time>0?source.last_key_time:2;
const sheet=document.createElement('canvas');sheet.width=1536;sheet.height=576;const sx=sheet.getContext('2d');let first,last,finite=true,boundsY=[Infinity,-Infinity],ranges={};
for(let i=0;i<=24;i++){c.pose(a,seconds*i/24);const matrix=Group.all.flatMap(g=>Array.from(g.mesh.matrixWorld.elements));finite=finite&&matrix.every(Number.isFinite);if(i===0)first=matrix;if(i===24)last=matrix;const b=c.bounds();boundsY=[Math.min(boundsY[0],b.min[1]),Math.max(boundsY[1],b.max[1])];
for(const g of Group.all){const r=ranges[g.name]||(ranges[g.name]={rotation_min:[Infinity,Infinity,Infinity],rotation_max:[-Infinity,-Infinity,-Infinity]});[g.mesh.rotation.x,g.mesh.rotation.y,g.mesh.rotation.z].forEach((v,j)=>{r.rotation_min[j]=Math.min(r.rotation_min[j],v*180/Math.PI);r.rotation_max[j]=Math.max(r.rotation_max[j],v*180/Math.PI);});}
if(i<24)sx.drawImage(c.render(center,span*1.08,'threequarter',192),i%8*192,Math.floor(i/8)*192);
}
c.save(sheet,s.species+'-'+label+'.png');motions.push({label,name:a.name,seconds,window_source:source.declared_length>0?'declared':source.last_key_time>0?'last_key':'2-second observation, NOT asserted loop length',frames:24,sample_count:25,finite,boundsY,end_matrix_delta:Math.max(...last.map((v,i)=>Math.abs(v-first[i]))),missing_bones:source.missing_bones,queries:source.queries,ranges});
}
return{species:s.species,success:true,blockbench_version:Blockbench.version,models_rendered:4,base_texture_inspected:true,layerPreview,bounds,animations_imported:imported.length,selection_namespace:modelClips.length?modelName:base.length?s.species:'UNRESOLVED_LIBRARY_FALLBACK',motions,note:'Selected clips only; no poser/state mixing, audio, particles or game runtime validation'};
}finally{if(ModelProject.all.includes(audit)){audit.saved=true;await audit.close(true);}ModelProject.all.find(p=>p.uuid===original)?.select();}
};
c.run=async(start,count)=>{if(c.status.running)throw Error('Batch already running');c.status={running:true,start,count,completed:0};try{for(let i=start;i<Math.min(start+count,manifest.samples.length);i++){const s=manifest.samples[i];c.status.current=s.species;let r;try{r=await c.inspect(s);}catch(e){r={species:s.species,success:false,error:String(e.stack||e)};}c.results=c.results.filter(x=>x.species!==s.species);c.results.push(r);fs.writeFileSync(recordPath,JSON.stringify(c.results,null,2));c.status.completed++;}}finally{c.status.running=false;ModelProject.all.find(p=>p.uuid===original)?.select();}return c.status;};
return JSON.stringify({ready:true,species:manifest.samples.length,original,existingResults:c.results.length});
})()
