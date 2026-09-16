const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const root='C:/Users/prasr/Downloads/naibra-app/naibra-app';
const ts=require(path.join(root,'node_modules/typescript'));
const mod={exports:{}};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,'src/components/ui/Report.tsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{module:mod,exports:mod.exports});
const scan=JSON.parse(fs.readFileSync('report_test_fixture.json','utf8'));
const html=mod.exports.buildReportHtml(scan,'','');
assert(html.includes('out of 100'));assert(html.includes('Detailed Scan Metrics'));assert(html.includes(String(scan.metrics.overall_score)));
console.log('PASS: original scored report generates full layout and metrics.');
