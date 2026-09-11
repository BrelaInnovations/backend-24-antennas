const fs = require('fs');
const path = require('path');
const root = 'C:/Users/prasr/Downloads/naibra-app/naibra-app';
const ts = require(path.join(root, 'node_modules/typescript'));
const manifest = require('./manifest.json');
const configFile = ts.readConfigFile(path.join(root, 'tsconfig.json'), ts.sys.readFile);
const config = ts.parseJsonConfigFileContent(configFile.config, ts.sys, root);
const options = { ...config.options, noEmit: true, incremental: false };
function check(overlay) {
  const host = ts.createCompilerHost(options);
  const originalRead = host.readFile.bind(host);
  if (overlay) host.readFile = file => {
    const relative = path.relative(root, file).replace(/\\/g, '/');
    if (manifest.some(m => m.path === relative)) return fs.readFileSync(path.join(__dirname, 'files', relative), 'utf8');
    return originalRead(file);
  };
  const program = ts.createProgram(config.fileNames, options, host);
  return ts.getPreEmitDiagnostics(program).map(d => ({
    file: d.file ? path.relative(root, d.file.fileName).replace(/\\/g, '/') : '',
    code: d.code, message: ts.flattenDiagnosticMessageText(d.messageText, '\n'),
    line: d.file && d.start !== undefined ? d.file.getLineAndCharacterOfPosition(d.start).line + 1 : 0,
  }));
}
const baseline = check(false);
const updated = check(true);
const key = d => `${d.file}:${d.code}:${d.message}`;
const existing = new Set(baseline.map(key));
const added = updated.filter(d => !existing.has(key(d)));
fs.writeFileSync(path.join(__dirname, 'typecheck.json'), JSON.stringify({ baseline, updated, added }, null, 2));
console.log(JSON.stringify({ baselineErrors: baseline.length, updatedErrors: updated.length, added }, null, 2));
process.exitCode = added.length ? 1 : 0;
