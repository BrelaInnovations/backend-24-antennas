const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const source = 'C:/Users/prasr/Downloads/naibra-app/naibra-app';
const stage = path.join(__dirname, 'files');
const manifest = [];
function edit(rel, transform) {
  const original = fs.readFileSync(path.join(source, rel), 'utf8');
  const updated = transform(original.replace(/\r\n/g, '\n'));
  fs.mkdirSync(path.dirname(path.join(stage, rel)), { recursive: true });
  fs.writeFileSync(path.join(stage, rel), updated);
  manifest.push({ path: rel, sha256: crypto.createHash('sha256').update(original).digest('hex') });
}
function replace(text, from, to) {
  if (!text.includes(from)) throw new Error('Missing anchor: ' + from.slice(0, 80));
  return text.replace(from, to);
}
edit('src/utils/api.ts', s => {
  s = replace(s, 'import axios from "axios";', 'import axios from "axios";\nimport Constants from "expo-constants";\nimport { Platform } from "react-native";');
  s = replace(s, 'const NAIBRA_API_BASE_URL = "http://172.17.236.44:8000/api";', `const expoHost = Constants.expoConfig?.hostUri?.split(":")[0];
const defaultHost = expoHost || (Platform.OS === "android" ? "10.0.2.2" : "localhost");
export const NAIBRA_API_BASE_URL = (
  process.env.EXPO_PUBLIC_API_URL || \`http://\${defaultHost}:8000/api\`
).replace(/\\/$/, "");`);
  s = replace(s, 'timeout: 60000, // real hardware sweeps can take a while -- see NUM_SWEEP_AVERAGES in server.py', 'timeout: 15000,');
  s = replace(s, 'let cachedScanId: string | null = null;', 'let cachedScanId: string | null = null;\nlet cachedScan: any = null;');
  s = s.replace(/\/\/ server\.py's POST[\s\S]*?let pendingRealScan/, '// Compatibility cache for callers that request the second view of a saved capture.\nlet pendingRealScan');
  s = replace(s, 'const cfg = await req(() => http.get("/config"));\n    const layout = await req(() => http.get("/antenna/layout"));', 'const [cfg, layout] = await Promise.all([\n      req(() => http.get("/config")), req(() => http.get("/antenna/layout")),\n    ]);');
  const start = s.indexOf('    // First call for this scan');
  const end = s.indexOf('\n  // Legacy single-call scan', start);
  s = s.slice(0, start) + `    if (params.scanId && params.scanId === cachedScanId && cachedScan) {
      return { ...cachedScan, scanned_side: params.side };
    }
    if (!pendingRealScan) {
      pendingRealScan = req(() => http.post("/scan/start", { label: params.label }, { timeout: 600000 }))
        .then((scan) => { cachedScanId = scan.id; cachedScan = scan; return scan; })
        .finally(() => { pendingRealScan = null; });
    }
    const scan = await pendingRealScan;
    return { ...scan, scanned_side: params.side };
  },
` + s.slice(end);
  return replace(s, 'req(() => http.post("/scan/start", { label }))', 'req(() => http.post("/scan/start", { label }, { timeout: 600000 }))');
});

// Only algorithm-tagged markers enter either production renderer. Old severity
// dots stay in saved records but cannot be mistaken for reconstructed locations.
edit('src/components/common/Dome3D.tsx', s => {
  s = replace(s, 's: number; c: string', 's?: number; c?: string; intensity?: number; source?: string');
  s = replace(s, '.filter((d) => visible[d.c])', '.filter((d) => d.source === "dmas-cf" && [d.x, d.y, d.z].every(Number.isFinite))');
  s = replace(s, '.map((d) => ({ ...proj(d), s: d.s, c: d.c }))', '.map((d) => proj(d))');
  s = replace(s, 'const r = 1.6 + d.s * 2.6 + depthNorm * 0.8;', 'const r = 2.4 + depthNorm * 0.8;');
  s = replace(s, 'fill={SEV_COLORS[d.c] || theme.colors.sevBaseline}', 'fill="#7C3AED"');
  return s.replace('severity dot cloud', 'DMAS-CF location markers');
});
edit('src/components/common/Dome/DomeSceneRN.tsx', s => {
  const start = s.indexOf('  const SEV_COLORS = useMemo(', s.indexOf('const FindingDots'));
  const end = s.indexOf('\nconst AntennaLines', start);
  if (start < 0 || end < 0) throw new Error('FindingDots missing');
  return s.slice(0, start) + `  const points = useMemo(() => dots.filter((d) =>
    d.source === "dmas-cf" && [d.x, d.y, d.z].every(Number.isFinite)
  ), [dots]);
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const color = useMemo(() => new THREE.Color(), []);
  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    points.forEach((dot, i) => {
      dummy.position.set(...toThree(dot));
      dummy.scale.setScalar(0.045);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      const active = !selectedQuadrant || getQuadrantFromArray(dot.x, dot.y) === selectedQuadrant;
      mesh.setColorAt(i, color.set(active ? "#7C3AED" : "#D8C6F5"));
    });
    mesh.count = points.length;
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }, [points, selectedQuadrant, dummy, color]);
  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, Math.max(1, points.length)]} frustumCulled={false}>
      <icosahedronGeometry args={[1, 1]} />
      <meshBasicMaterial />
    </instancedMesh>
  );
});
` + s.slice(end);
});
edit('src/screens/common/DomeScreen.tsx', s => {
  s = replace(s, '    const fetcher = scanId ?', '    let active = true;\n    setErr(null);\n    setScan(null);\n    const fetcher = scanId ?');
  s = replace(s, '      .then((s) => {', '      .then((s) => {\n        if (!active) return;');
  s = replace(s, '      .catch((e) => setErr(e.message));', '      .catch((e) => { if (active) setErr(e.message); });\n    return () => { active = false; };');
  const start = s.indexOf('          {/* severity filter chips */}');
  const end = s.indexOf('          {/* Scan Configuration */}', start);
  s = s.slice(0, start) + `          <Text style={styles.sectionTitle}>DMAS-CF localization</Text>
          <View style={styles.metricCard}>
            <View style={{ flex: 1 }}>
              <Text style={styles.metricTitle}>
                {sideData.display_mode === "localization" ? sideData.status : "Legacy scan — capture a new DMAS-CF scan"}
              </Text>
              <Text style={styles.metricSub}>{sideData.dot_count ?? 0} displayed locations</Text>
              {sideData.peak_location_cm && (
                <Text style={styles.metricSub}>
                  Peak (cm): x {sideData.peak_location_cm.x.toFixed(2)}, y {sideData.peak_location_cm.y.toFixed(2)}, z {sideData.peak_location_cm.z.toFixed(2)}
                </Text>
              )}
              <Text style={styles.metricSub}>Uniform dots mark reconstructed voxel positions. Both views share one physical capture.</Text>
              {sideData.sampled && <Text style={styles.metricSub}>Showing a spatial sample of {sideData.selected_voxel_count} selected voxels.</Text>}
            </View>
          </View>

` + s.slice(end);
  s = replace(s, 'const scoreText = scan?.[s] ? scan[s].score : "Not scanned";', 'const scoreText = scan?.[s] ? `${scan[s].dot_count ?? 0} locations` : "Not scanned";');
  s = s.replace('const CATS = ["high", "medium", "low", "baseline"] as const;\n', '');
  const vs = s.indexOf('  const [visible, setVisible]');
  const ve = s.indexOf('  const [showAnts', vs);
  s = s.slice(0, vs) + s.slice(ve);
  const ts = s.indexOf('  const toggleCat');
  const te = s.indexOf('  const sideData', ts);
  s = s.slice(0, ts) + s.slice(te);
  s = s.replace('              visible={visible}\n', '');
  s = s.replace('  const counts = sideData?.dot_counts || {};\n  const m = scan?.metrics;\n', '');
  return s;
});
edit('src/screens/common/Scan/component/ScanResultHero.tsx', s => {
  const a = s.indexOf('  const score = isSingle');
  const b = s.indexOf('\n  return (', a);
  s = s.slice(0, a) + `  const score = result?.left?.dot_count ?? result?.right?.dot_count ?? 0;
  const verdict = result?.metrics?.verdict_label ?? "Localization unavailable";
  const verdictColor = theme.colors.brandDark;
` + s.slice(b);
  return s.replace('Breast health analysis', 'DMAS-CF localization').replace('Health Score', 'Displayed locations · shared capture')
    .replace('const sideScore = result?.[side]?.score;', 'const sideScore = result?.[side]?.dot_count ?? 0;');
});
edit('src/screens/common/Scan/component/ScanResultDomes.tsx', s => s.replace('{result[side]?.score || 0}', '{result[side]?.dot_count ?? 0} locations'));
edit('src/screens/user/HomeScreen.tsx', s => {
  const a = s.indexOf('  const verdictColor = hasMetrics');
  const b = s.indexOf('\n\n', a);
  s = s.slice(0, a) + '  const verdictColor = theme.colors.brandDark;' + s.slice(b);
  s = replace(s, '{isSingleDome\n                  ? `${scan?.left ? "Left" : "Right"} Breast Score`\n                  : "Breast Health Score"}', 'DMAS-CF displayed locations');
  return s.replace('{displayScore}', '{scan?.left?.dot_count ?? scan?.right?.dot_count ?? "—"}')
    .replace('{displayVerdict}', '{scan?.display_mode === "localization" ? displayVerdict : "Legacy scan"}')
    .replace('{scan.left.score}', '{scan.left.dot_count ?? "—"}')
    .replace('{scan.right.score}', '{scan.right.dot_count ?? "—"}');
});
edit('src/screens/user/RepositoryScreen.tsx', s => {
  s = replace(s, '  left_score: number;', '  left_dot_count?: number;\n  right_dot_count?: number;\n  display_mode?: string;\n  left_score: number;');
  return s.replace('{item.left_score}', '{item.left_dot_count ?? "—"} locations')
    .replace('{item.right_score}', '{item.right_dot_count ?? "—"} locations')
    .replace('Δ {item.asymmetry}', '{item.display_mode === "localization" ? "DMAS-CF" : "Legacy"}')
    .replace('{item.overall_score}', '{item.left_dot_count ?? "—"}')
    .replace('{item.verdict_label}', '{item.display_mode === "localization" ? item.verdict_label : "Legacy scan"}');
});
edit('src/screens/common/CompareScreen.tsx', s => {
  s = s.replace('{s.overall_score} · {s.verdict_label}', '{s.display_mode === "localization" ? s.verdict_label : "Legacy scan"}');
  const a = s.indexOf('          {/* deltas */}');
  const b = s.indexOf('\n        </ScrollView>', a);
  return s.slice(0,a) + `          <View style={styles.deltaCard}>
            <Text style={styles.deltaTitle}>DMAS-CF location comparison</Text>
            <Text>{data.insight}</Text>
          </View>` + s.slice(b);
});
edit('src/components/ui/Report.tsx', s => {
  return replace(s, 'export function buildReportHtml(r: any, leftImage: string, rightImage: string) {', `export function buildReportHtml(r: any, leftImage: string, rightImage: string) {
  // Export the same location-only result shown in the app.
  const escape = (value: unknown) => String(value ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] || c));
  return \`<!doctype html><html><head><meta charset="utf-8"><style>
    body{font:14px Arial;color:#231b35;padding:24px}h1{color:#7c3aed}
    section{break-inside:avoid;margin:24px 0}img{width:260px;height:260px;object-fit:contain}
    </style></head><body><h1>DMAS-CF localization</h1>
    <p>\${escape(r.label)} · \${escape(r.created_at)}</p>
    <p>Dots show reconstructed locations. Both views share one physical capture.</p>
    \${(["left", "right"] as const).filter(side => r[side]).map(side => {
      const result = r[side]; const peak = result.peak_location_cm;
      const image = side === "left" ? leftImage : rightImage;
      return \`<section><h2>\${side === "left" ? "Left" : "Right"} view</h2>
        <p>Status: \${escape(result.display_mode === "localization" ? result.status : "Legacy scan — capture a new DMAS-CF scan")}</p>
        <p>Displayed locations: \${escape(result.dot_count ?? 0)}</p>
        \${peak ? \`<p>Peak (cm): x \${escape(peak.x)}, y \${escape(peak.y)}, z \${escape(peak.z)}</p>\` : ""}
        \${image ? \`<img src="\${escape(image)}" />\` : ""}</section>\`;
    }).join("")}</body></html>\`;
}

function buildLegacyReportHtml(r: any, leftImage: string, rightImage: string) {`);
});
edit('src/screens/onboarding/OnboardingScreen.tsx', s => s.replace('live risk severity coloring', 'DMAS-CF location markers'));
edit('src/store/scanProcessStore.ts', s => {
  const start = s.indexOf('export const useScanProcessStore');
  return s.slice(0, start) + `let generation = 0;
let requestRunning = false;

export const useScanProcessStore = create<ScanProcessState>((set, get) => {
  const clearTimer = () => { if (get().timerRef) clearInterval(get().timerRef); };
  const reset = (side: ScanSide = "left") => {
    generation++;
    clearTimer();
    set({ phase: "ready", selectedSide: side, elapsed: 0, currentScanId: null,
      scannedSides: [], result: null, error: null, timerRef: null });
  };
  return {
    phase: "ready", duration: 60, elapsed: 0, currentScanId: null,
    selectedSide: "left", scannedSides: [], result: null, error: null,
    deviceMode: "simulated", timerRef: null,
    setSelectedSide: (side) => set({ selectedSide: side }),
    setDuration: (duration) => set({ duration }),
    updateDeviceMode: (deviceMode) => set({ deviceMode }),
    setError: (error) => set({ error }),
    initScanSession: async (side) => { await get().startScan(side); },
    executeScanProcess: async () => { await get().startScan(get().selectedSide); },
    saveScanResult: async (side) => { await get().startScan(side); },
    startScan: async (side) => {
      if (requestRunning) {
        set({ error: "A capture is still running. Wait for it to finish before starting another." });
        return;
      }
      requestRunning = true;
      const token = ++generation;
      clearTimer();
      set({ phase: "initializing", selectedSide: side, elapsed: 0,
        error: null, result: null, scannedSides: [], currentScanId: null });
      try {
        await api.initScanSession(side);
        if (token !== generation) return;
        const started = Date.now();
        const timerRef = setInterval(() => {
          if (token === generation) set({ elapsed: (Date.now() - started) / 1000 });
        }, 250);
        set({ phase: "scanning", timerRef });
        // One backend request acquires and reconstructs the physical sweep.
        // The backend's two views share this acquisition.
        const scan = await api.startScan(new Date().toLocaleString());
        if (token !== generation) return;
        const sides: ("left" | "right")[] = side === "both" ? ["left", "right"] : [side];
        set({ result: { ...scan, scanned_side: side }, currentScanId: scan.id,
          scannedSides: sides, phase: "done" });
      } catch (error: any) {
        if (token === generation) set({ phase: "error", error: error.message || "Scan failed" });
      } finally {
        requestRunning = false;
        if (token === generation) { clearTimer(); set({ timerRef: null }); }
      }
    },
    // Leaving the view invalidates late responses; physical capture may finish
    // on the server because the hardware API has no abort endpoint.
    cancelScan: () => reset(get().selectedSide),
    rescanSide: (side) => reset(side),
    switchSide: (side) => reset(side),
    resetScan: () => reset(),
  };
});
`;
});
edit('src/screens/common/Scan/index.tsx', s => {
  s = replace(s, '<CountdownRing progress={progress} remaining={remaining} />', '<ActivityIndicator size="large" color={theme.colors.brandDark} />');
  s = replace(s, 'Scanning {selectedSide === "both" ? "both sides" : selectedSide}{" "}\n                · {activeIds || "…"}', 'Acquiring sweep and reconstructing DMAS-CF');
  s = replace(s, '{Math.round(progress * 100)}% · sweep {freqStart}–{freqStop} GHz', '{Math.floor(elapsed)}s elapsed · sweep {freqStart}–{freqStop} GHz');
  s = s.replace('Switch to {selectedSide === "left" ? "Right" : "Left"} Side', 'Leave capture view');
  const infoStart = s.indexOf('              <Text style={styles.antennaInfo}>');
  const infoEnd = s.indexOf('              </Text>', infoStart);
  if (infoStart >= 0 && infoEnd >= 0) s = s.slice(0, infoStart) + '              <Text style={styles.antennaInfo}>Waiting for the hardware result; capture continues if you leave.</Text>' + s.slice(infoEnd + '              </Text>'.length);
  return s;
});
fs.writeFileSync(path.join(__dirname, 'manifest.json'), JSON.stringify(manifest, null, 2));
console.log(`Prepared ${manifest.length} frontend files`);
