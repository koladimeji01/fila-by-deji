'use strict';
const fs=require('node:fs');
const path=require('node:path');
const root=__dirname,dst=path.join(root,'dist');
const files=['index.html','css/style.css','js/admin.js','assets/fila-logo.svg','assets/favicon.svg'];
fs.rmSync(dst,{recursive:true,force:true});
for(const name of files){
 const src=path.join(root,name),target=path.join(dst,name);
 if(!fs.existsSync(src))throw Error('Missing admin asset: '+name);
 fs.mkdirSync(path.dirname(target),{recursive:true});fs.copyFileSync(src,target);
}
if(fs.existsSync(path.join(dst,'backend'))||fs.existsSync(path.join(dst,'.env'))){
 throw Error('Private backend or secrets must never ship to the admin frontend');
}
console.log('FÌLÀ business administration: isolated build with '+files.length+' files');
