const fs=require('fs'),path=require('path');
const root='C:/Users/prasr/Downloads/naibra-app/naibra-app';
const ts=require(path.join(root,'node_modules/typescript'));
for(const file of ['src/components/common/Dome3D.tsx','src/components/common/Dome/DomeSceneRN.tsx','src/screens/common/BridgeScreen.tsx','src/screens/common/DomeScreen.tsx','src/screens/common/Scan/component/ScanResultHero.tsx']) {
const result=ts.transpileModule(fs.readFileSync(path.join(root,file),'utf8'),{fileName:file,reportDiagnostics:true,compilerOptions:{jsx:ts.JsxEmit.ReactJSX}});
if(result.diagnostics.some(d=>d.category===ts.DiagnosticCategory.Error)) throw Error(file);
}
console.log('Changed frontend files: syntax checks passed.');
