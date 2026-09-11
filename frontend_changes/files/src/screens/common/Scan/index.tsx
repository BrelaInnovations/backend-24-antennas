import React, { useRef, useMemo, RefObject, Suspense } from "react";
import {
  useWindowDimensions,
  View,
  Text,
  Pressable,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import ViewShot from "react-native-view-shot";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { UserStackParamList } from "../../../navigation/types";
import { useScanFlow } from "./hooks/useScan";
import { usePdfExport } from "./hooks/useExport";
import { theme } from "../../../theme";
import { ScreenWrapper } from "../../../components/layout/ScreenWrapper";
import { ScanHeader } from "./component/ScanHeader";
import { ScanReadyView } from "./component/ScanReadyView";
import { ScanningView } from "./component/ScanningView";
import { ScanDoneView } from "./component/ScanDoneView";
import { AcquiringSweepsIndicator } from "./component/AcquiringSweepsIndicato";
import { CountdownRing } from "./component/CountdownRing";
import { Ionicons } from "@expo/vector-icons";
import DomeSceneRN from "../../../components/common/Dome/DomeSceneRN";

type Props = NativeStackScreenProps<UserStackParamList, "Scan">;

export const ScanScreen: React.FC<Props> = ({ navigation }) => {
  const { width } = useWindowDimensions();
  const leftRef = useRef<ViewShot>(null);
  const rightRef = useRef<ViewShot>(null);

  const {
    phase,
    duration,
    setDuration,
    elapsed,
    layout,
    result,
    error,
    setError,
    bridge,
    resultRef,
    start,
    cancel,
    resetScan,
    selectedSide,
    setSelectedSide,
    scannedSides,
    rescan,
    switchSide,
  } = useScanFlow();

  const handleClose = () => {
    resetScan();
    navigation.goBack();
  };

  const handleNewScan = () => {
    resetScan();
  };

  const { exporting, exportPdf } = usePdfExport(
    resultRef,
    leftRef as RefObject<ViewShot>,
    rightRef as RefObject<ViewShot>,
    setError,
  );
  // Derived values — memoized to avoid recompute on every render
  const antennas = useMemo(() => layout?.antennas || [], [layout]);
  const sequence: string[] = useMemo(
    () => antennas.map((a: any) => a.id),
    [antennas],
  );

  const checkMap: Record<string, boolean> = useMemo(() => {
    const map: Record<string, boolean> = {};
    (result?.antenna_check || []).forEach(
      (r: any) => (map[r.id] = r.responding),
    );
    return map;
  }, [result]);

  const progress = Math.min(1, elapsed / duration);
  const activeIdx = Math.min(
    sequence.length - 1,
    Math.floor(progress * sequence.length),
  );
  const remaining = Math.max(0, Math.ceil(duration - elapsed));
  const pulsePhase = (elapsed % 0.7) / 0.7;
  const domeSize = Math.min(width - theme.spacing2.xl * 2, 330);

  const activeAntenna = useMemo(
    () => antennas.find((a: any) => a.id === sequence[activeIdx]),
    [antennas, sequence, activeIdx],
  );
  const freqStart = layout?.freq_start_mhz / 1000 || 2;
  const freqStop = layout?.freq_stop_mhz / 1000 || 6;

  // Dynamic configuration display

  const numProngs = layout?.num_prongs || 12;
  const antennasPerProng = layout?.antennas_per_prong || 4;
  const currentProng = activeAntenna?.prong ?? 0;

  const currentAntennaInProng = useMemo(() => {
    if (!activeAntenna) return 0;
    return (
      antennas
        .filter((a: any) => a.prong === currentProng)
        .findIndex((a: any) => a.id === activeAntenna.id) + 1
    );
  }, [antennas, currentProng, activeAntenna]);

  const enabledAntennas = useMemo(
    () => antennas.filter((a: any) => a.enabled).length,
    [antennas],
  );
  const totalAntennas = antennas.length;

  const antennaLength = activeAntenna?.length_mm || 0;
  const antennaFreq = activeAntenna?.frequency_mhz || 0;

  const activeIds = useMemo(() => [sequence[activeIdx]], [sequence, activeIdx]);

  return (
    <ScreenWrapper hideHeader={true}>
      <ScanHeader phase={phase} duration={duration} onClose={handleClose} />

      {phase === "scanning" && (
        <>
          <View style={styles.countRow}>
            <ActivityIndicator size="large" color={theme.colors.brandDark} />
            <View style={{ flex: 1 }}>
              <Text style={styles.statusPill}>
                Acquiring sweep and reconstructing DMAS-CF
              </Text>
              <Text style={styles.statusSub}>
                {Math.floor(elapsed)}s elapsed · sweep {freqStart}–{freqStop} GHz
              </Text>
              <Text style={styles.configInfo}>
                {numProngs}×{antennasPerProng} array · {enabledAntennas}/
                {totalAntennas} active
              </Text>
              <Text style={styles.antennaInfo}>Waiting for the hardware result; capture continues if you leave.</Text>
            </View>
          </View>
          {selectedSide !== "both" && (
            <View style={styles.sideSwitchRow}>
              <Pressable
                testID="scan-switch-side"
                style={styles.sideSwitchBtn}
                onPress={() =>
                  switchSide(selectedSide === "left" ? "right" : "left")
                }
              >
                <Ionicons
                  name="swap-horizontal"
                  size={18}
                  color={theme.colors.brandDark}
                />
                <Text style={styles.sideSwitchText}>
                  Leave capture view
                </Text>
              </Pressable>
              {scannedSides.includes(
                selectedSide === "left" ? "right" : "left",
              ) && (
                <View style={styles.sideIndicator}>
                  <Ionicons
                    name="checkmark-circle"
                    size={14}
                    color={theme.colors.success}
                  />
                  <Text style={styles.sideIndicatorText}>
                    {selectedSide === "left" ? "Right" : "Left"} scanned
                  </Text>
                </View>
              )}
            </View>
          )}
        </>
      )}
      {phase !== "done" && (
        <View style={styles.domeWrap}>
          {/* <ScanDome
            mode={phase}
            antennas={antennas}
            activeId={phase === "scanning" ? sequence[activeIdx] : undefined}
            pulsePhase={pulsePhase}
          /> */}
          <Suspense fallback={<ActivityIndicator />}>
            <DomeSceneRN
              size={domeSize}
              antennas={antennas}
              showAntennas
              showBeams={phase === "scanning"}
              activeIds={
                phase === "scanning" && activeIds ? activeIds : undefined
              }
              pulsePhase={pulsePhase}
            />
          </Suspense>
        </View>
      )}
      {phase === "ready" && (
        <ScanReadyView
          antennas={antennas}
          layout={layout}
          domeSize={domeSize}
          duration={duration}
          setDuration={setDuration}
          error={error}
          bridge={bridge}
          onManageBridge={() => navigation.push("Bridge")}
          onStart={start}
          selectedSide={selectedSide}
          setSelectedSide={setSelectedSide}
          scannedSides={scannedSides}
        />
      )}

      {phase === "scanning" && (
        <ScanningView
          sequence={sequence}
          activeIdx={activeIdx}
          checkMap={checkMap}
          result={result}
          onStop={cancel}
        />
      )}

      {phase === "done" && result && (
        <ScanDoneView
          result={result}
          error={error}
          exporting={exporting}
          leftRef={leftRef as RefObject<ViewShot>}
          rightRef={rightRef as RefObject<ViewShot>}
          onExportPdf={exportPdf}
          onOpenDome={(side) =>
            navigation.navigate("Dome", { scanId: result.id, side })
          }
          onDone={handleClose}
          scannedSides={scannedSides}
          onRescan={rescan}
          onNewScan={handleNewScan}
          scanDuration={duration}
        />
      )}

      {phase === "error" && (
        <View
          style={{
            padding: theme.spacing2.xl,
            alignItems: "center",
            justifyContent: "center",
            flex: 1,
          }}
        >
          <Text
            style={{
              fontFamily: theme.typography.fontFamily.xbold,
              fontSize: 18,
              color: theme.colors.error,
              marginBottom: theme.spacing2.md,
            }}
          >
            Scan Error
          </Text>
          <Text
            style={{
              fontFamily: theme.typography.fontFamily.reg,
              fontSize: 14,
              color: theme.colors.ink,
              textAlign: "center",
              marginBottom: theme.spacing2.lg,
            }}
          >
            {error || "An unknown error occurred during scanning"}
          </Text>
          <Pressable
            style={{
              padding: theme.spacing2.md,
              backgroundColor: theme.colors.surface2,
              borderRadius: theme.radius.pill,
              borderWidth: 1,
              borderColor: theme.colors.border,
            }}
            onPress={handleClose}
          >
            <Text
              style={{
                fontFamily: theme.typography.fontFamily.bold,
                fontSize: 14,
                color: theme.colors.ink,
              }}
            >
              Go Back
            </Text>
          </Pressable>
        </View>
      )}

      {(phase === "scanning" ||
        phase === "initializing" ||
        phase === "processing") &&
        !result &&
        elapsed > 3 && <AcquiringSweepsIndicator />}
    </ScreenWrapper>
  );
};

const styles = StyleSheet.create({
  countRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing2.md,
    paddingHorizontal: theme.spacing2.lg,
    marginTop: theme.spacing2.sm,
  },
  statusPill: {
    fontFamily: theme.typography.fontFamily.xbold,
    fontSize: 14,
    color: theme.colors.brandDark,
  },
  statusSub: {
    fontFamily: theme.typography.fontFamily.reg,
    fontSize: 12,
    color: theme.colors.inkSoft,
    marginTop: 2,
  },
  configInfo: {
    fontFamily: theme.typography.fontFamily.bold,
    fontSize: 11,
    color: theme.colors.inkSoft,
    marginTop: 4,
  },
  antennaInfo: {
    fontFamily: theme.typography.fontFamily.reg,
    fontSize: 11,
    color: theme.colors.brandDark,
    marginTop: 2,
  },
  domeWrap: { alignItems: "center" },
  sideSwitchRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: theme.spacing2.md,
    paddingHorizontal: theme.spacing2.lg,
    marginTop: theme.spacing2.md,
  },
  sideSwitchBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing2.sm,
    paddingHorizontal: theme.spacing2.lg,
    height: 40,
    borderRadius: theme.radius.pill,
    borderWidth: 1.5,
    borderColor: theme.colors.brandDark,
    backgroundColor: theme.colors.surface,
  },
  sideSwitchText: {
    fontFamily: theme.typography.fontFamily.bold,
    fontSize: 13,
    color: theme.colors.brandDark,
  },
  sideIndicator: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  sideIndicatorText: {
    fontFamily: theme.typography.fontFamily.reg,
    fontSize: 11,
    color: theme.colors.inkSoft,
  },
});
