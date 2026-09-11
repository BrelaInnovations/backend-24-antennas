import { create } from "zustand";
import { api } from "../utils/api";

export type Phase =
  "ready" | "initializing" | "scanning" | "processing" | "done" | "error";
export type ScanSide = "left" | "right" | "both";

interface ScanResult {
  id: string;
  created_at: string;
  label: string;
  left: any;
  right: any;
  metrics: any;
  antennas: any[];
  sequence: string[];
  antenna_check: any[];
  config_snapshot: any;
  scanned_side: ScanSide;
}

interface ScanProcessState {
  // Phase management
  phase: Phase;
  duration: number;
  elapsed: number;

  // Scan data
  currentScanId: string | null;
  selectedSide: ScanSide;
  scannedSides: ("left" | "right")[];
  result: ScanResult | null;

  // Error handling
  error: string | null;

  // Device connection info
  deviceMode: "bluetooth" | "wired" | "simulated";

  // Timer reference
  timerRef: any;

  // Actions
  setSelectedSide: (side: ScanSide) => void;
  setDuration: (duration: number) => void;

  // Phase 1: Initialize scan session
  initScanSession: (side: ScanSide) => Promise<void>;

  // Phase 2: Execute scanning process through device
  executeScanProcess: () => Promise<void>;

  // Phase 3: Save scan result (create or update)
  saveScanResult: (side: "left" | "right") => Promise<void>;

  // Control actions
  startScan: (side: ScanSide) => Promise<void>;
  cancelScan: () => void;
  rescanSide: (side: "left" | "right") => void;
  switchSide: (side: "left" | "right") => void;

  // Error handling
  setError: (error: string | null) => void;
  resetScan: () => void;
  updateDeviceMode: (mode: "bluetooth" | "wired" | "simulated") => void;
}

let generation = 0;
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
