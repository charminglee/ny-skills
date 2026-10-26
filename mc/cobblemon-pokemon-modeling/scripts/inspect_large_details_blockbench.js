/* Load after inspect_shading_blockbench.js. cbShade.supplement(name, cubeIndices)
 * creates local, unlit evidence with the full surrounding model still visible.
 * Cube indices must come from this manifest's native surfaces, not another import.
 */
(()=>{
const d=window.cbShade,fs=require('fs');
if(!d?.manifest)throw Error('Initialize cbShade first');
d.supplement=async(name,indices=[])=>{
if(d.status.running||d.supplementRunning)throw Error('Another native batch is running');
if(Project.uuid!==d.original.uuid)throw Error('Expected the protected original project');
const s=d.manifest.samples.find(x=>x.species===name);if(!s)throw Error('Unknown species');
d.supplementRunning=true;newProject(Formats.bedrock);const audit=Project;audit.name='LARGE_DETAIL_'+name;
try{
Codecs.bedrock.parse(JSON.parse(fs.readFileSync(s.model,'utf8')));audit.save_path='';audit.export_path='';
const t=new Texture({name:name+'_read_only'}).fromDataURL('data:image/png;base64,'+fs.readFileSync(s.texture).toString('base64')).add(false);
await new Promise(r=>t.load(r));t.path='';
for(const c of Cube.all)for(const f of Object.values(c.faces))if(f.texture!==null)f.texture=t.uuid;
d.rest();
if(indices.some(i=>!Number.isInteger(i)||!Cube.all[i]))throw Error('Invalid cube index');
const mats=[...new Set(Cube.all.flatMap(c=>Array.isArray(c.mesh.material)?c.mesh.material:[c.mesh.material]))];
if(mats.some(m=>!m.uniforms?.SHADE))throw Error('Unlit toggle unavailable');
mats.forEach(m=>m.uniforms.SHADE.value=false);
const selections=[Cube.all,...indices.map(i=>[Cube.all[i]])],cv=document.createElement('canvas');cv.width=960;cv.height=selections.length*500;
const ctx=cv.getContext('2d');ctx.fillStyle='#dfe6e9';ctx.fillRect(0,0,cv.width,cv.height);
for(let j=0;j<selections.length;j++){
const b=d.bounds(selections[j]),center=b.min.map((v,k)=>(v+b.max[k])/2),dim=b.max.map((v,k)=>v-b.min[k]),span=Math.max(dim[1],Math.hypot(dim[0],dim[2]))*1.35;
for(let k=0;k<2;k++)ctx.drawImage(d.render(center,span,k?[.8,.3,1]:[.7,1,-1],480),k*480,j*500);
ctx.fillStyle='#223847';ctx.font='18px sans-serif';ctx.fillText(j===0?name+' / high front + high back':name+' / cube '+indices[j-1]+' / '+selections[j][0].parent.name,10,j*500+491);
}
fs.mkdirSync(d.out+'/closeups',{recursive:true});
fs.writeFileSync(d.out+'/closeups/'+name+'.png',Buffer.from(cv.toDataURL().split(',')[1],'base64'));
return {species:name,views:selections.length*2};
}finally{audit.saved=true;await audit.close(true);d.restore();d.supplementRunning=false;}
};
return {ready:true,original:d.original.uuid};
})()
