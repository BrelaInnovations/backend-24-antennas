const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const root='C:/Users/prasr/Downloads/naibra-app/naibra-app';
const ts=require(path.join(root,'node_modules/typescript'));
let now=0, observed=[];
class ClockDate extends Date { static now(){return now;} }
const m={exports:{}};
const api={initScanSession:async()=>({}), startScan:async()=>({id:'demo',simulated:true})};
const code=ts.transpileModule(fs.readFileSync(path.join(root,'src/store/scanProcessStore.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
vm.runInNewContext(code,{exports:m.exports,module:m,Date:ClockDate,
setInterval:()=>1,clearInterval:()=>{},setTimeout:(fn,ms)=>{observed.push(m.exports.useScanProcessStore.getState().phase);now+=ms;fn();},
require:n=>n==='../utils/api'?{api}:n==='./authStore'?{useAuthStore:{getState:()=>({userProfile:{mode:'user'}})}}:require(path.join(root,'node_modules',n))});
(async()=>{const s=m.exports.useScanProcessStore;await s.getState().startScan('left');assert.equal(now,60000);assert(observed.every(p=>p==='scanning'));assert.equal(s.getState().phase,'done');s.getState().setDuration(12);now=0;await s.getState().startScan('right');assert.equal(now,12000);console.log('PASS: Full waits 60 seconds; Quick waits 12 seconds; results stay hidden during simulation.');})().catch(e=>{console.error(e);process.exitCode=1;});
