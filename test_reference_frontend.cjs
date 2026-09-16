const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');
const root = 'C:/Users/prasr/Downloads/naibra-app/naibra-app';
const ts = require(path.join(root, 'node_modules/typescript'));
let mode = 'developer', calls = [];
const api = { initScanSession: async () => ({}), startScan: async (...args) => { calls.push(args); return {id:'test'}; } };
const moduleMock = {exports:{}};
const source = fs.readFileSync(path.join(root, 'src/store/scanProcessStore.ts'), 'utf8');
vm.runInNewContext(ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText, {
  exports: moduleMock.exports, module: moduleMock, setInterval, clearInterval, Date,
  require: name => name === '../utils/api' ? {api} : name === './authStore' ? {useAuthStore:{getState:()=>({userProfile:{mode}})}} : require(path.join(root,'node_modules',name))
});
(async () => {
  const store = moduleMock.exports.useScanProcessStore;
  store.getState().setTruePositionEnabled(true);
  await store.getState().startScan('left');
  assert.equal(calls.length, 0, 'Incomplete input must not acquire hardware');
  for (const [axis,value] of Object.entries({x:'-2',y:'2',z:'3'})) store.getState().setTruePositionInput(axis,value);
  await store.getState().startScan('left');
  assert.equal(JSON.stringify(calls[0][1]), JSON.stringify({x:-2,y:2,z:3}));
  assert.equal(store.getState().phase, 'done');
  mode = 'user';
  await store.getState().startScan('right');
  assert.equal(calls[1][1], undefined, 'Ordinary mode must not submit developer inputs');
  console.log('PASS: invalid input blocks acquisition; developer coordinates submitted; user mode omits reference.');
})().catch(e => { console.error(e); process.exitCode=1; });
