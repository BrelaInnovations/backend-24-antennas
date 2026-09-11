const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('C:/Users/prasr/Downloads/naibra-app/naibra-app/node_modules/typescript');
function load(relative, mocks) {
  const file = path.join(__dirname, 'files', relative);
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
    fileName: file,
  }).outputText;
  const exports = {};
  vm.runInNewContext(code, { exports, require: name => {
    if (!(name in mocks)) throw new Error(`Unexpected import: ${name}`);
    return mocks[name];
  }, process: { env: {} }, setInterval, clearInterval, Date, console });
  return exports;
}
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => {resolve=a; reject=b;}); return {promise, resolve, reject}; };
const tick = () => new Promise(resolve => setImmediate(resolve));
async function main() {
  let posts = 0, next = deferred(), config;
  const {api, NAIBRA_API_BASE_URL} = load('src/utils/api.ts', {
    axios: { create: c => { config=c; return {
      post: () => { posts++; return next.promise; },
      get: async url => ({data: url === '/antenna/layout' ? {antennas: []} : {}}),
    }; } },
    'expo-constants': {expoConfig: {hostUri:'192.168.1.40:8081'}},
    'react-native': {Platform: {OS:'android'}},
  });
  assert.equal(NAIBRA_API_BASE_URL, 'http://192.168.1.40:8000/api');
  assert.equal(config.timeout, 15000);
  const first = api.finalizeScan({side:'left'});
  const duplicate = api.finalizeScan({side:'left'});
  assert.equal(posts, 1);
  next.resolve({data:{id:'uuid-one', left:{dots:[]},right:{dots:[]}}});
  assert.equal((await first).id, 'uuid-one');
  await duplicate;
  assert.equal((await api.finalizeScan({side:'right',scanId:'uuid-one'})).id, 'uuid-one');
  assert.equal(posts, 1);
  next=deferred();
  const failed=api.finalizeScan({side:'left'});
  next.reject({response:{data:{detail:'No hardware'}}});
  await assert.rejects(failed, /No hardware/);
  next=deferred();
  const retry=api.finalizeScan({side:'left'});
  next.resolve({data:{id:'uuid-two'}});
  assert.equal((await retry).id, 'uuid-two');

  // Run the store with a minimal synchronous Zustand harness and a controlled API.
  let state, calls = 0, capture=deferred();
  const storeApi = {
    initScanSession: async () => ({id:'session'}),
    startScan: () => { calls++; return capture.promise; },
  };
  load('src/store/scanProcessStore.ts', {
    zustand: {create: init => {
      state = init(update => { state={...state,...(typeof update==='function'?update(state):update)}; }, () => state);
      return {getState:()=>state};
    }}, '../utils/api': {api:storeApi},
  });
  const both=state.startScan('both'); await tick();
  assert.equal(state.phase,'scanning');
  assert.equal(calls,1); // both views require one real acquisition
  await state.startScan('both'); assert.equal(calls,1);
  capture.resolve({id:'actual-uuid',left:{dots:[]},right:{dots:[]}}); await both;
  assert.equal(state.phase,'done');
  assert.equal(state.scannedSides.join(','),'left,right');
  assert.equal(state.timerRef,null);
  state.rescanSide('right'); capture=deferred();
  const rescan=state.startScan('right'); await tick();
  assert.equal(calls,2);
  state.cancelScan();
  capture.resolve({id:'late-response'}); await rescan;
  assert.equal(state.phase,'ready'); assert.equal(state.result,null);
  capture=deferred();
  const errorRun=state.startScan('left'); await tick();
  capture.reject(new Error('Device disconnected')); await errorRun;
  assert.equal(state.phase,'error'); assert.equal(state.timerRef,null);
  assert.equal(state.error,'Device disconnected');

  const {buildReportHtml} = load('src/components/ui/Report.tsx', {});
  const html = buildReportHtml({label:'<test>',created_at:'2026-09-09',left:{
    display_mode:'localization',status:'localized',dot_count:2,peak_location_cm:{x:1,y:2,z:3},
  }}, 'data:image/png;base64,test', '');
  assert.match(html,/&lt;test&gt;/); assert.match(html,/Peak \(cm\): x 1, y 2, z 3/);
  assert.doesNotMatch(html,/Health Score|Healthy|High-risk/);
  console.log('Frontend tests passed: URL, duplicate calls, cached side, retry, real acquisition, rescan, cancellation, errors, export.');
}
main().catch(error => { console.error(error); process.exitCode=1; });
