/* Set CB_SHADING_OUTPUT, eval in Blockbench MCP, then cbShade.run(start,count).
 * Imports read-only sources into disposable projects. No animation evaluation.
 * Native UVs and transformed face vertices are recorded, including internal faces.
 */
(()=>{
const fs=require('fs'),path=require('path'),out=window.CB_SHADING_OUTPUT;
if(!out)throw Error('Set CB_SHADING_OUTPUT');
const manifest=JSON.parse(fs.readFileSync(path.join(out,'manifest.json'),'utf8'));
const original=Project,mode=Modes.selected.id,time=Timeline.time,selectedAnimation=Animation.selected;
const playing=Animation.all.filter(a=>a.playing),wasSaved=Project.saved;
for(const dir of ['native','surfaces','backup'])fs.mkdirSync(path.join(out,dir),{recursive:true});
const snapshot=path.join(out,'backup','active-project-before.bbmodel');
if(!fs.existsSync(snapshot))fs.writeFileSync(snapshot,Codecs.project.compile());
window.cbShade={out,manifest,original,results:fs.existsSync(path.join(out,'native-results.json'))?JSON.parse(fs.readFileSync(path.join(out,'native-results.json'),'utf8')):[],status:{running:false}};
const d=cbShade;
d.restore=()=>{original.select();Modes.options[mode]?.select();if(mode==='animate'&&selectedAnimation){Animation.all.forEach(a=>a.playing=false);selectedAnimation.select();playing.forEach(a=>a.playing=true);Timeline.setTime(time);Animator.preview();}Project.saved=wasSaved;};
d.save=(cv,name)=>fs.writeFileSync(path.join(out,'native',name),Buffer.from(cv.toDataURL().split(',')[1],'base64'));
d.rest=()=>{Timeline.pause();Modes.options.edit.select();Canvas.updateAll();Canvas.updateAllBones();Animator.showDefaultPose();Project.model_3d.updateMatrixWorld(true);};
d.bounds=cubes=>{const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];for(const c of cubes){const a=c.mesh.geometry.attributes.position;for(let i=0;i<a.count;i++)new THREE.Vector3().fromBufferAttribute(a,i).applyMatrix4(c.mesh.matrixWorld).toArray().forEach((v,k)=>{min[k]=Math.min(min[k],v);max[k]=Math.max(max[k],v);});}return {min,max};};
d.render=(center,span,dir,size=256)=>{
const cam=new THREE.OrthographicCamera(-span/2,span/2,span/2,-span/2,.01,span*12+100);
cam.position.fromArray(center).add(new THREE.Vector3(...dir).normalize().multiplyScalar(span*4));cam.lookAt(new THREE.Vector3(...center));cam.updateMatrixWorld(true);
const r=Preview.selected.renderer,sz=r.getSize(new THREE.Vector2()),ratio=r.getPixelRatio(),bg=Canvas.scene.background,hidden=[];
Canvas.scene.traverse(o=>{if(o.visible&&(o.isLine||o.type==='GridHelper'||o===Canvas.ground||/grid|axes/i.test(o.name))){o.visible=false;hidden.push(o);}});
try{r.setPixelRatio(1);r.setSize(size,size,false);Canvas.scene.background=new THREE.Color('#dfe6e9');r.render(Canvas.scene,cam);const cv=document.createElement('canvas');cv.width=cv.height=size;cv.getContext('2d').drawImage(r.domElement,0,0);return cv;}
finally{Canvas.scene.background=bg;hidden.forEach(o=>o.visible=true);r.setPixelRatio(ratio);r.setSize(sz.x,sz.y,false);}
};
d.inspect=async s=>{
newProject(Formats.bedrock);const audit=Project;audit.name='SHADING_READONLY_'+s.species;
try{
Codecs.bedrock.parse(JSON.parse(fs.readFileSync(s.model,'utf8')));audit.save_path='';audit.export_path='';
if(Cube.all.length!==s.model_stats.cubes)throw Error('Cube count mismatch');
const tex=new Texture({name:s.species+'_study'}).fromDataURL('data:image/png;base64,'+fs.readFileSync(s.texture).toString('base64')).add(false);
await new Promise(r=>tex.load(r));tex.path='';tex.saved=true;
for(const c of Cube.all)for(const f of Object.values(c.faces))if(f.texture!==null)f.texture=tex.uuid;
d.rest();
const faces=[],faceOrder=['east','west','up','down','south','north'];
for(const [ci,c]of Cube.all.entries()){
const a=c.mesh.geometry.attributes,normalMatrix=new THREE.Matrix3().getNormalMatrix(c.mesh.matrixWorld);
if(a.position.count!==24)throw Error('Unexpected cube vertex layout');
for(let j=0;j<6;j++){
const key=faceOrder[j],f=c.faces[key],vertices=[];
for(let k=0;k<4;k++){const i=j*4+k;vertices.push({p:new THREE.Vector3().fromBufferAttribute(a.position,i).applyMatrix4(c.mesh.matrixWorld).toArray(),uv:[a.uv.getX(i)*tex.width,(1-a.uv.getY(i))*tex.height]});}
const p=vertices.map(v=>new THREE.Vector3(...v.p));
const area=p[1].clone().sub(p[0]).cross(p[2].clone().sub(p[0])).length();
if(area<1e-7||!f.texture||Math.abs((f.uv[2]-f.uv[0])*(f.uv[3]-f.uv[1]))<1e-7)continue;
const ancestry=[];let parent=c.parent;while(parent&&parent!=='root'){ancestry.push(parent.name);parent=parent.parent;}
faces.push({cube:ci,bone:c.parent.name,ancestry,face:key,uv:f.uv.slice(),rotation:f.rotation,normal:new THREE.Vector3().fromBufferAttribute(a.normal,j*4).applyNormalMatrix(normalMatrix).toArray(),area,vertices});
}}
const bounds=d.bounds(Cube.all),center=bounds.min.map((v,i)=>(v+bounds.max[i])/2),dim=bounds.max.map((v,i)=>v-bounds.min[i]);
const span=Math.max(dim[1],Math.hypot(dim[0],dim[2]))*1.2;
const dirs=[[0,0,-1],[1,0,0],[0,0,1],[.7,.25,-1]],labels=['front','side','back','3/4'];
const sheet=document.createElement('canvas');sheet.width=1024;sheet.height=568;const cx=sheet.getContext('2d');cx.fillStyle='#dfe6e9';cx.fillRect(0,0,1024,568);
const mats=[...new Set(Cube.all.flatMap(c=>Array.isArray(c.mesh.material)?c.mesh.material:[c.mesh.material]))];
if(mats.some(m=>!m.uniforms?.SHADE))throw Error('Unlit shader toggle unavailable');
const old=mats.map(m=>m.uniforms.SHADE.value);
try{for(let row=0;row<2;row++){
mats.forEach(m=>m.uniforms.SHADE.value=row===1);
dirs.forEach((dir,i)=>{cx.drawImage(d.render(center,span,dir),i*256,row*284);cx.fillStyle='#223847';cx.font='14px sans-serif';cx.fillText((row?'lit ':'unlit ')+labels[i],i*256+8,row*284+274);});
}}finally{mats.forEach((m,i)=>m.uniforms.SHADE.value=old[i]);}
d.save(sheet,s.species+'-shading.png');
const result={species:s.species,success:true,blockbench:Blockbench.version,cubes:Cube.all.length,bones:Group.all.length,faces:faces.length,bounds,views:8,texture_size:[tex.width,tex.height],base_only:true,layers_not_applied:(s.layers||[]).map(l=>l.name),scope:'Bind pose; native SHADE off/on; raw base texture; surfaces include occluded/internal faces; no runtime material or poser validation'};
fs.writeFileSync(path.join(out,'surfaces',s.species+'.json'),JSON.stringify({...result,surfaces:faces}));return result;
}finally{audit.saved=true;await audit.close(true);d.restore();}
};
d.run=async(start,count)=>{if(d.status.running)throw Error('Batch running');d.status={running:true,start,count,completed:0};const batch=[];
try{for(let i=start;i<Math.min(start+count,manifest.samples.length);i++){
const s=manifest.samples[i];d.status.current=s.species;
if(d.results.some(r=>r.species===s.species&&r.success))continue;
let r;try{r=await d.inspect(s);}catch(e){r={species:s.species,success:false,error:String(e.stack||e)};}
d.results=d.results.filter(x=>x.species!==s.species);d.results.push(r);fs.writeFileSync(path.join(out,'native-results.json'),JSON.stringify(d.results,null,2));batch.push({species:r.species,success:r.success,error:r.error});d.status.completed++;
}}finally{d.status.running=false;d.restore();}return batch;};
return {ready:true,samples:manifest.samples.length,original:original.uuid,completed:d.results.length};
})()
