// Real API layer -- talks to the FastAPI/Mongo server (server.py) over HTTP.
// Replaces the old offline-mock version of this file (which read/wrote the
// JSON files in ./exports/ as a local DB). Every exported function keeps the
// SAME name and signature the mock had, so no screen/store that imports
// `api` needed to change -- only what happens inside each function changed.

import axios from "axios";
import Constants from "expo-constants";
import { Platform } from "react-native";

// ---------------------------------------------------------------------------
// Base URL
// ---------------------------------------------------------------------------
// CHANGE THIS to your machine's LAN IP (not "localhost" -- on a phone/Expo
// Go, "localhost" means the phone itself, not your computer) and the port
// uvicorn is running on. Find your IP with `ipconfig` (Windows) or
// `ifconfig`/`ip addr` (Mac/Linux). Example: "http://192.168.1.42:8000/api".
// If you're only ever running in a web browser on the SAME machine as the
// backend, "http://localhost:8000/api" also works.
const expoHost = Constants.expoConfig?.hostUri?.split(":")[0];
const defaultHost = expoHost || (Platform.OS === "android" ? "10.0.2.2" : "localhost");
export const NAIBRA_API_BASE_URL = (
  process.env.EXPO_PUBLIC_API_URL || `http://${defaultHost}:8000/api`
).replace(/\/$/, "");

const http = axios.create({
  baseURL: NAIBRA_API_BASE_URL,
  timeout: 15000,
});

// Unwraps FastAPI's response / lets axios's own error surface as a normal
// Error with a useful message, since screens do `catch (e) { e.message }`.
async function req<T = any>(fn: () => Promise<{ data: T }>): Promise<T> {
  try {
    const res = await fn();
    return res.data;
  } catch (err: any) {
    const detail =
      err?.response?.data?.detail || err?.message || "Request failed";
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
}

// ---------------------------------------------------------------------------
// In-memory cache for the two-phase (left/right) scan flow
// ---------------------------------------------------------------------------
// Compatibility cache for callers that request the second view of a saved capture.
let pendingRealScan: Promise<any> | null = null;
let cachedScanId: string | null = null;
let cachedScan: any = null;

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export const api = {
  // ---- config / antennas -----------------------------------------------
  getConfig: async () => req(() => http.get("/config")),

  updateConfig: async (body: any) => req(() => http.put("/config", body)),

  resetConfig: async () => req(() => http.post("/config/reset")),

  antennaLayout: async () => req(() => http.get("/antenna/layout")),

  antennaTest: async () => req(() => http.post("/antenna/test")),

  // ---- scan flow ---------------------------------------------------------
  // Phase 1: no real backend equivalent (server.py captures everything in
  // one atomic call, it doesn't have a "session" concept) -- so this just
  // fetches the current config/antenna layout, which is genuinely useful
  // for the UI to show before scanning starts, and fabricates a LOCAL
  // session id (never sent to the backend, just used to track UI state
  // the same way the old mock's session.id did).
  initScanSession: async (side?: "left" | "right" | "both") => {
    const [cfg, layout] = await Promise.all([
      req(() => http.get("/config")), req(() => http.get("/antenna/layout")),
    ]);
    return {
      id: `session-${Date.now().toString(36)}`,
      created_at: new Date().toISOString(),
      antennas: layout.antennas,
      sequence: layout.antennas
        .filter((a: any) => a.enabled)
        .map((a: any) => a.id),
      config_snapshot: cfg,
      side: side || "both",
      device_mode: cfg.connection_mode || "simulated",
    };
  },

  // Phase 2: no real per-side capture endpoint exists -- the actual sweep
  // happens inside POST /api/scan/start (called from finalizeScan below).
  // This stays a no-op placeholder so scanProcessStore's timer/UI still
  // runs, exactly like it did against the mock.
  executeDeviceScan: async (sessionId: string, side: "left" | "right") => {
    return { id: sessionId, scanned_at: new Date().toISOString(), side, status: "completed" };
  },

  // Phase 3: this is where the real hardware/backend call happens.
  finalizeScan: async (params: {
    sessionId?: string;
    scanId?: string;
    side: "left" | "right";
    label?: string;
  }) => {
    if (params.scanId && params.scanId === cachedScanId && cachedScan) {
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

  // Legacy single-call scan -- maps directly onto the real atomic endpoint.
  startScan: async (label?: string) => req(() => http.post("/scan/start", { label }, { timeout: 600000 })),

  listScans: async () => req(() => http.get("/scans")),

  latestScan: async () => req(() => http.get("/scans/latest")),

  getScan: async (id: string) => req(() => http.get(`/scans/${id}`)),

  deleteScan: async (id: string) => req(() => http.delete(`/scans/${id}`)),

  // NOTE: server.py has no PATCH/label-rename endpoint for a scan yet.
  // Leaving this as a clear error instead of silently no-op'ing, so it's
  // obvious in the UI if RepositoryScreen's rename ever gets tapped rather
  // than failing to persist silently.
  updateScanLabel: async (_id: string, _label: string) => {
    throw new Error(
      "Renaming a saved scan isn't supported by the backend yet " +
        "(no PATCH /api/scans/{id} endpoint in server.py).",
    );
  },

  compare: async (a: string, b: string) => req(() => http.get(`/compare/${a}/${b}`)),

  // ---- user / periods / avatar -------------------------------------------
  getUser: async () => req(() => http.get("/user")),

  updateUser: async (body: any) => req(() => http.put("/user", body)),

  listPeriods: async () => req(() => http.get("/periods")),

  logPeriod: async (start_date: string, notes = "") =>
    req(() => http.post("/periods", { start_date, notes })),

  deletePeriod: async (id: string) => req(() => http.delete(`/periods/${id}`)),

  cycleStatus: async () => req(() => http.get("/cycle/status")),

  avatarStatus: async () => req(() => http.get("/avatar/status")),

  // ---- bridge (hardware connect) -----------------------------------------
  bridgeScan: async () => req(() => http.post("/bridge/scan")),

  bridgeConnect: async (transport: string, device = "") =>
    req(() => http.post("/bridge/connect", { transport, device })),

  bridgeStatus: async () => req(() => http.get("/bridge/status")),
};

export default api;