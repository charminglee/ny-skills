/* Run in Blockbench via MCP. Isolated read-only source previews, resumable records. */
(()=>{
const fs=require('fs'),path=require('path');
const dir=window.CB_FULL_OUTPUT;if(!dir)throw Error('Set CB_FULL_OUTPUT');
const manifest=JSON.parse(fs.readFileSync(path.join(dir,'manifest.json'),'utf8'));
const original=Project.uuid;const folders=['native','native-records','backup'];for(const f of folders)fs.mkdirSync(path.join(dir,f),{recursive:true});
const backup=path.join(dir,'backup','workbench-before.bbmodel');if(!fs.existsSync(backup))fs.writeFileSync(backup,Codecs.project.compile());
window.cbFull={dir,manifest,original,status:{running:false},version:Blockbench.version};const R=cbFull;
R.save=(cv,file)=>fs.writeFileSync(path.join(dir,'native',file),Buffer.from(cv.toDataURL().split(',')[1],'base64'));
R.image=p=>new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('load image '+p));im.src='data:image/png;base64,'+fs.readFileSync(p).toString('base64');});
R.rest=()=>{Timeline.pause();Animation.all.forEach(a=>a.playing=false);Modes.options.edit.select();Canvas.updateAll();Canvas.updateAllBones();Animator.showDefaultPose();Project.model_3d.updateMatrixWorld(true);};
R.bounds=()=>{Project.model_3d.updateMatrixWorld(true);const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];for(const c of Cube.all){const a=c.mesh.geometry.attributes.position;for(let i=0;i<a.count;i++){const v=new THREE.Vector3().fromBufferAttribute(a,i).applyMatrix4(c.mesh.matrixWorld);[v.x,v.y,v.z].forEach((x,k)=>{min[k]=Math.min(min[k],x);max[k]=Math.max(max[k],x);});}}return{min,max};};
R.render=(center,span,dir,size=224,lit=false)=>{
 const camera=new THREE.OrthographicCamera(-span/2,span/2,span/2,-span/2,.01,span*10+100);camera.position.fromArray(center).add(new THREE.Vector3(...dir).normalize().multiplyScalar(span*3));camera.lookAt(new THREE.Vector3(...center));camera.updateMatrixWorld(true);
 const r=Preview.selected.renderer,old=new THREE.Vector2();r.getSize(old);const ratio=r.getPixelRatio(),bg=Canvas.scene.background,hidden=[],shade=[];
 Canvas.scene.traverse(o=>{if(o.visible&&(o.isLine||o.type==='GridHelper'||o===Canvas.ground||o.name==='grid'||o.name==='grid_group')){hidden.push(o);o.visible=false;}});
 for(const t of Texture.all){const m=t.getMaterial?.();if(m?.uniforms?.SHADE){shade.push([m,m.uniforms.SHADE.value]);m.uniforms.SHADE.value=lit;}}
 try{r.setPixelRatio(1);r.setSize(size,size,false);Canvas.scene.background=new THREE.Color('#343945');r.render(Canvas.scene,camera);const cv=document.createElement('canvas');cv.width=cv.height=size;cv.getContext('2d').drawImage(r.domElement,0,0);return cv;}
 finally{Canvas.scene.background=bg;hidden.forEach(o=>o.visible=true);shade.forEach(([m,v])=>m.uniforms.SHADE.value=v);r.setPixelRatio(ratio);r.setSize(old.x,old.y,false);}
};
R.pose=(a,t)=>{Modes.options.animate.select();Timeline.pause();Animation.all.forEach(x=>x.playing=false);a.select();a.playing=true;Timeline.setTime(t);Animator.preview();Project.model_3d.updateMatrixWorld(true);};
R.inspect=async s=>{
 newProject(Formats.bedrock);const audit=Project;audit.name='READONLY_'+s.id;
 const record={id:s.id,source_hash:s.source_hash,success:false,version:Blockbench.version,texture:s.texture,notes:['Binding pose and isolated clips, NOT game poser blending.','Layers use static first-frame source-over, NOT emissive/translucent shader proof.']};
 try{
  Codecs.bedrock.parse(JSON.parse(fs.readFileSync(s.model,'utf8')));audit.save_path='';audit.export_path='';
  if(Cube.all.length!==s.cubes||Group.all.length!==s.bones)throw Error('Geometry import count mismatch');
  const cv=document.createElement('canvas');cv.width=Project.texture_width;cv.height=Project.texture_height;const cx=cv.getContext('2d');
  if(s.texture){const im=await R.image(s.texture);cv.width=im.width;cv.height=im.height;cx.drawImage(im,0,0);
    const layers=s.selected_variation?.layers||[];record.layers=[];
    for(const l of layers){const res=typeof l.texture==='string'?l.texture:l.texture?.frames?.[0];const f=s.selected_variation.layer_files.find(x=>x.resource===res&&x.exists);if(f){const li=await R.image(f.file);cx.drawImage(li,0,0);record.layers.push({resource:res,emissive:!!l.emissive,translucent:!!l.translucent});}}
  }else{cx.fillStyle='#bdc5d1';cx.fillRect(0,0,cv.width,cv.height);record.notes.push('NO RESOLVED TEXTURE: neutral geometry-only preview');}
  const tex=new Texture({name:'isolated-study.png',render_sides:'double'}).fromDataURL(cv.toDataURL()).add(false);
  await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Texture load timeout')),10000);tex.load(()=>{clearTimeout(timer);resolve();});});tex.path='';tex.saved=true;
  for(const c of Cube.all)for(const f of Object.values(c.faces))if(f.texture!==null)f.texture=tex.uuid;
  R.rest();const bounds=R.bounds(),center=bounds.min.map((v,i)=>(v+bounds.max[i])/2),dim=bounds.max.map((v,i)=>v-bounds.min[i]),span=Math.max(dim[1],Math.hypot(dim[0],dim[2]),1)*1.23;
  record.bounds=bounds;record.surfaces=[];
  const pixels=cx.getImageData(0,0,cv.width,cv.height).data;
  for(const [i,c] of Cube.all.entries())for(const [name,f] of Object.entries(c.faces)){
    if(f.texture===null)continue;const uv=f.uv;if(!uv||uv[0]===uv[2]||uv[1]===uv[3])continue;
    const minU=Math.min(uv[0],uv[2]),maxU=Math.max(uv[0],uv[2]),minV=Math.min(uv[1],uv[3]),maxV=Math.max(uv[1],uv[3]);const count={};let alpha=0,total=0;
    for(let y=Math.max(0,Math.floor(minV));y<Math.min(cv.height,Math.ceil(maxV));y++)for(let x=Math.max(0,Math.floor(minU));x<Math.min(cv.width,Math.ceil(maxU));x++){const p=(y*cv.width+x)*4;total++;if(pixels[p+3]>0){alpha++;const k=[pixels[p],pixels[p+1],pixels[p+2],pixels[p+3]].join(',');count[k]=(count[k]||0)+1;}}
    record.surfaces.push({cube:i,bone:c.parent?.name,face:name,size:c.size(),uv:uv.slice(),rotation:f.rotation,opaquePixels:alpha,totalPixels:total,colors:Object.keys(count).length,dominant:alpha?Math.max(...Object.values(count))/alpha:0,uvOutside:minU<0||minV<0||maxU>cv.width||maxV>cv.height});
  }
  const view=document.createElement('canvas');view.width=896;view.height=472;const vx=view.getContext('2d');vx.fillStyle='#343945';vx.fillRect(0,0,view.width,view.height);
  const dirs=[[0,0,-1],[1,0,0],[0,0,1],[.65,.2,-1]];
  dirs.forEach((d,i)=>{vx.drawImage(R.render(center,span,d,224,false),i*224,0);vx.drawImage(R.render(center,span,d,224,true),i*224,224);});vx.font='14px sans-serif';vx.fillStyle='#ffffff';vx.fillText(s.id+' / top: texture / bottom: shaded'+(!s.texture?' / UNRESOLVED TEXTURE':''),8,467);R.save(view,s.id+'-views.png');
  const files=[...new Set(s.animations.map(a=>a.file))];for(const f of files)AnimationCodec.codecs.bedrock.loadFile({name:path.basename(f),path:'',json:JSON.parse(fs.readFileSync(f,'utf8'))});
  record.motions=[];
  for(const source of s.animations){
    const missing=source['missing_bones_'+s.modelname]||[];
    if(source.unresolved_variables.length||missing.length){record.motions.push({name:source.name,rendered:false,reason:'unresolved runtime inputs or unmatched bones',queries:source.unresolved_variables,missing});continue;}
    const a=Animation.all.find(x=>x.name===source.name);if(!a){record.motions.push({name:source.name,rendered:false,reason:'import not found'});continue;}
    let first,last,finite=true,minY=Infinity;const motionBounds={min:[Infinity,Infinity,Infinity],max:[-Infinity,-Infinity,-Infinity]};
    for(let i=0;i<=24;i++){R.pose(a,source.window*i/24);const matrices=Group.all.flatMap(g=>Array.from(g.mesh.matrixWorld.elements));finite=finite&&matrices.every(Number.isFinite);if(i===0)first=matrices;if(i===24)last=matrices;const b=R.bounds();for(let k=0;k<3;k++){motionBounds.min[k]=Math.min(motionBounds.min[k],b.min[k]);motionBounds.max[k]=Math.max(motionBounds.max[k],b.max[k]);}minY=Math.min(minY,b.min[1]);}
    const mc=motionBounds.min.map((v,k)=>(v+motionBounds.max[k])/2),md=motionBounds.max.map((v,k)=>v-motionBounds.min[k]);const ms=Math.max(md[1],Math.hypot(md[0],md[2]),1)*1.22;
    const sheet=document.createElement('canvas');sheet.width=864;sheet.height=288;const sx=sheet.getContext('2d');
    for(let i=0;i<12;i++){R.pose(a,source.window*i/12);sx.drawImage(R.render(mc,ms,[.65,.16,-1],144,false),i%6*144,Math.floor(i/6)*144);}
    const filename=s.id+'--'+source.name.replace(/[^a-zA-Z0-9_.-]/g,'_')+'.png';R.save(sheet,filename);
    record.motions.push({name:source.name,rendered:true,file:filename,frames:12,samples:25,window:source.window,window_source:source.window_source,finite,minY,endMatrixDelta:Math.max(...last.map((v,i)=>Math.abs(v-first[i]))),bounds:motionBounds,semantics:'isolated animation, no runtime variable substitution or poser blending'});
  }
  record.success=true;return record;
 }catch(e){record.error=String(e.stack||e);return record;}
 finally{if(ModelProject.all.includes(audit)){audit.saved=true;await audit.close(true);}ModelProject.all.find(p=>p.uuid===original)?.select();}
};
R.run=async(start,count)=>{if(R.status.running)throw Error('Already running');R.status={running:true,start,count,completed:0,skipped:0,failed:0};try{for(let i=start;i<Math.min(start+count,manifest.models.length);i++){const s=manifest.models[i],file=path.join(dir,'native-records',s.id+'.json');R.status.current=s.id;
 if(fs.existsSync(file)){const old=JSON.parse(fs.readFileSync(file,'utf8'));if(old.success&&old.source_hash===s.source_hash&&old.texture===s.texture){R.status.skipped++;continue;}}
 const record=await R.inspect(s);fs.writeFileSync(file,JSON.stringify(record));R.status.completed++;if(!record.success)R.status.failed++;fs.writeFileSync(path.join(dir,'native-status.json'),JSON.stringify(R.status));}
 }finally{R.status.running=false;fs.writeFileSync(path.join(dir,'native-status.json'),JSON.stringify(R.status));ModelProject.all.find(p=>p.uuid===original)?.select();}return R.status;};
return JSON.stringify({ready:true,models:manifest.models.length,original});
})();
