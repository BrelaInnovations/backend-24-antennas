import { Ionicons } from "@expo/vector-icons";
import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
  Platform,
} from "react-native";
import DomeScene, {
  SnapshotAction,
  type Quadrant,
} from "../../components/common/Dome/DomeSceneRN";
import { api } from "../../utils/api";
import { theme } from "../../theme";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { UserStackParamList } from "../../navigation/types";
import { ScreenWrapper } from "../../components/layout/ScreenWrapper";
import { buildReportHtml } from "../../components/ui/Report";
import * as Print from "expo-print";
import * as Sharing from "expo-sharing";


type Props = NativeStackScreenProps<UserStackParamList, "Dome">;

export const DomeScreen: React.FC<Props> = ({ navigation, route }) => {
  const { width } = useWindowDimensions();
  const { scanId, side: initialSide } = route.params || {};
  const [scan, setScan] = useState<any>(null);
  const [side, setSide] = useState<"left" | "right">(initialSide || "left");
  const [showAnts, setShowAnts] = useState(false);
  const [selectedQuadrant, setSelectedQuadrant] = useState<Quadrant | null>(
    null,
  );
  const [err, setErr] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const resultRef = useRef<any>(null);

  const domeRef = useRef<SnapshotAction | null>(null);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setErr(null);
    setScan(null);
    const fetcher = scanId ? api.getScan(scanId) : api.latestScan();
    fetcher
      .then((s) => {
        if (!active) return;
        resultRef.current = s;
        setScan(s);
        if (initialSide && s[initialSide]) {
          setSide(initialSide);
        } else if (s.left) {
          setSide("left");
        } else if (s.right) {
          setSide("right");
        }
      })
      .catch((e) => { if (active) setErr(e.message); });
    return () => { active = false; };
  }, [scanId, initialSide]);
  const sideData = scan?.[side] || { dots: [], dot_counts: {}, score: 0 };

  const exportPdf = async () => {
    setExporting(true);

    const previousSide = side;

    try {
      let leftImg = "";
      let rightImg = "";

      if (scan?.left) {
        setSide("left");
        await new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        );
        leftImg = (await domeRef.current?.capture()) ?? "";
      }

      if (scan?.right) {
        setSide("right");
        await new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        );
        rightImg = (await domeRef.current?.capture()) ?? "";
      }
      const html = buildReportHtml(resultRef.current, leftImg, rightImg);

      const { uri } = await Print.printToFileAsync({
        html,
      });

      await Sharing.shareAsync(uri, {
        mimeType: "application/pdf",
      });
    } catch (e: any) {
      console.log(e);
      setError(e.message);
    } finally {
      setSide(previousSide);
      setExporting(false);
    }
  };

  return (
    <ScreenWrapper hideHeader={true}>
      <View style={styles.header}>
        <Pressable
          testID="dome-back-button"
          style={styles.backBtn}
          onPress={() =>
            navigation.canGoBack()
              ? navigation.goBack()
              : navigation.navigate("UserHome")
          }
        >
          <Ionicons name="arrow-back" size={22} color={theme.colors.ink} />
        </Pressable>
        <Text style={styles.title}>Breast Dome</Text>
        <Pressable
          testID="dome-toggle-antennas"
          style={styles.backBtn}
          onPress={() => setShowAnts((s) => !s)}
        >
          <Ionicons
            name={showAnts ? "wifi" : "wifi-outline"}
            size={20}
            color={showAnts ? theme.colors.brandDark : theme.colors.inkFaint}
          />
        </Pressable>
      </View>

      {err ? (
        <View style={styles.center}>
          <Text style={styles.errText}>{err}</Text>
        </View>
      ) : !scan ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={theme.colors.brandDark} />
          <Text style={styles.loadingText}>Loading 3D model…</Text>
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={{ paddingBottom: 40 }}
          showsVerticalScrollIndicator={false}
        >
          {/* side toggle */}
          <View style={styles.segment}>
            {(["left", "right"] as const).map((s) => {
              const isAvailable = Boolean(scan?.[s]);
              const scoreText = scan?.[s] ? `${scan[s].dot_count ?? 0} locations` : "Not scanned";
              return (
                <Pressable
                  key={s}
                  testID={`dome-side-${s}`}
                  style={[
                    styles.segBtn,
                    side === s && styles.segBtnOn,
                    !isAvailable && { opacity: 0.5 },
                  ]}
                  onPress={() => isAvailable && setSide(s)}
                  disabled={!isAvailable}
                >
                  <Text
                    style={[styles.segText, side === s && styles.segTextOn]}
                  >
                    {s === "left" ? "Left" : "Right"} · {scoreText}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          {/* dome */}
          <View style={styles.domeCard}>
            <DomeScene
              size={Math.min(
                width - theme.spacing2.lg * 2 - theme.spacing2.md,
                360,
              )}
              dots={sideData.dots || []}
              antennas={scan.antennas || []}
              showAntennas={showAnts}
              testID="dome-main-view"
              onQuadrantSelect={setSelectedQuadrant}
              selectedQuadrant={selectedQuadrant}
              snapshotActionRef={domeRef}
            />
            <Text style={styles.hint}>
              drag to rotate · tap quadrants for 3D slice view · patch antennas
              shown in lavender
            </Text>
          </View>

          <Text style={styles.sectionTitle}>DMAS-CF localization</Text>
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

          {/* Scan Configuration */}
          {scan.config_snapshot && (
            <View style={styles.configCard}>
              <Text style={styles.sectionTitle}>Scan Configuration</Text>
              <View style={styles.configRow}>
                <View style={styles.configItem}>
                  <Text style={styles.configLabel}>Array Geometry</Text>
                  <Text style={styles.configValue}>
                    {scan.config_snapshot.num_prongs} prongs ×{" "}
                    {scan.config_snapshot.antennas_per_prong} antennas
                  </Text>
                </View>
                <View style={styles.configItem}>
                  <Text style={styles.configLabel}>Frequency Range</Text>
                  <Text style={styles.configValue}>
                    {scan.config_snapshot.freq_start_mhz / 1000}–
                    {scan.config_snapshot.freq_stop_mhz / 1000} GHz
                  </Text>
                </View>
              </View>
              <View style={styles.configRow}>
                <View style={styles.configItem}>
                  <Text style={styles.configLabel}>Sweep Points</Text>
                  <Text style={styles.configValue}>
                    {scan.config_snapshot.sweep_points}
                  </Text>
                </View>
                <View style={styles.configItem}>
                  <Text style={styles.configLabel}>Scanned Side</Text>
                  <Text style={styles.configValue}>
                    {scan.scanned_side === "left"
                      ? "Left"
                      : scan.scanned_side === "right"
                        ? "Right"
                        : "Both"}
                  </Text>
                </View>
              </View>
              <View style={styles.configRow}>
                <View style={styles.configItem}>
                  <Text style={styles.configLabel}>Connection Mode</Text>
                  <Text style={styles.configValue}>
                    {scan.config_snapshot.connection_mode}
                  </Text>
                </View>
                <View style={styles.configItem}>
                  <Text style={styles.configLabel}>Device</Text>
                  <Text style={styles.configValue}>
                    {scan.config_snapshot.device_name || "Default"}
                  </Text>
                </View>
              </View>
            </View>
          )}
        </ScrollView>
      )}

      <View
        style={{
          flexDirection: "row",
          gap: theme.spacing2.md,
          paddingHorizontal: theme.spacing2.lg,
          marginTop: theme.spacing2.lg,
        }}
      >
        <Pressable
          testID="scan-export-pdf"
          style={[styles.resBtnAlt, exporting && { opacity: 0.6 }]}
          onPress={exportPdf}
          disabled={exporting}
        >
          {exporting ? (
            <ActivityIndicator size="small" color={theme.colors.brandDark} />
          ) : (
            <>
              <Ionicons
                name="document-text-outline"
                size={20}
                color={theme.colors.brandDark}
              />
              <Text style={styles.resBtnAltText}>Export PDF report</Text>
            </>
          )}
        </Pressable>
      </View>
      {error && (
        <Text
          style={[
            styles.errText,
            { textAlign: "center", marginTop: theme.spacing2.sm },
          ]}
        >
          {error}
        </Text>
      )}
    </ScreenWrapper>
  );
};

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.colors.surface },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: theme.spacing2.sm,
  },
  backBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: theme.colors.surface3,
    alignItems: "center",
    justifyContent: "center",
  },
  title: {
    fontFamily: theme.typography.fontFamily.xbold,
    fontSize: 18,
    color: theme.colors.ink,
  },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: theme.spacing2.sm,
  },
  loadingText: {
    fontFamily: theme.typography.fontFamily.reg,
    fontSize: 13,
    color: theme.colors.inkSoft,
  },
  errText: {
    fontFamily: theme.typography.fontFamily.bold,
    fontSize: 14,
    color: theme.colors.error,
  },
  segment: {
    flexDirection: "row",
    backgroundColor: theme.colors.surface3,
    borderRadius: theme.radius.pill,
    padding: 4,
  },
  segBtn: {
    flex: 1,
    height: 40,
    borderRadius: theme.radius.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  segBtnOn: { backgroundColor: theme.colors.brandDark },
  segText: {
    fontFamily: theme.typography.fontFamily.bold,
    fontSize: 14,
    color: theme.colors.inkSoft,
  },
  segTextOn: { color: "#fff" },
  domeCard: {
    alignItems: "center",
    marginTop: theme.spacing2.md,
    backgroundColor: theme.colors.surface2,
    borderRadius: theme.radius.lg,
    paddingVertical: theme.spacing2.sm,
    borderWidth: 1,
    borderColor: theme.colors.border,
    ...theme.shadow.card,
  },
  hint: {
    fontFamily: theme.typography.fontFamily.reg,
    fontSize: 11,
    color: theme.colors.inkFaint,
    marginBottom: 6,
    marginHorizontal: 12,
  },
  chipRow: {
    gap: theme.spacing2.sm,
    alignItems: "center",
  },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    height: 36,
    paddingHorizontal: theme.spacing2.md,
    borderRadius: theme.radius.pill,
    borderWidth: 1.5,
    flexShrink: 0,
  },
  chipDot: { width: 9, height: 9, borderRadius: 5 },
  chipText: {
    fontFamily: theme.typography.fontFamily.bold,
    fontSize: 12,
    color: theme.colors.ink,
  },
  chipHint: {
    fontFamily: theme.typography.fontFamily.reg,
    fontSize: 11,
    color: theme.colors.inkFaint,
    textAlign: "center",
    marginTop: theme.spacing2.sm,
  },
  sectionTitle: {
    fontFamily: theme.typography.fontFamily.xbold,
    fontSize: 16,
    color: theme.colors.ink,
    marginTop: theme.spacing2.lg,
    marginBottom: theme.spacing2.md,
  },
  metricCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing2.md,
    marginHorizontal: theme.spacing2.lg,
    marginBottom: theme.spacing2.md,
    backgroundColor: theme.colors.surface2,
    borderRadius: theme.radius.lg,
    padding: theme.spacing2.lg,
    borderWidth: 1,
    borderColor: theme.colors.border,
    ...theme.shadow.card,
  },
  metricTitle: {
    fontFamily: theme.typography.fontFamily.xbold,
    fontSize: 14,
    color: theme.colors.ink,
  },
  metricSub: {
    fontFamily: theme.typography.fontFamily.reg,
    fontSize: 12,
    color: theme.colors.inkSoft,
    marginTop: 2,
  },
  configCard: {
    marginHorizontal: theme.spacing2.lg,
    marginBottom: theme.spacing2.md,
    backgroundColor: theme.colors.surface2,
    borderRadius: theme.radius.lg,
    padding: theme.spacing2.lg,
    borderWidth: 1,
    borderColor: theme.colors.border,
    ...theme.shadow.card,
  },
  configRow: {
    flexDirection: "row",
    gap: theme.spacing2.md,
    marginBottom: theme.spacing2.md,
  },
  configItem: {
    flex: 1,
  },
  configLabel: {
    fontFamily: theme.typography.fontFamily.bold,
    fontSize: 11,
    color: theme.colors.inkSoft,
    marginBottom: 2,
  },
  configValue: {
    fontFamily: theme.typography.fontFamily.bold,
    fontSize: 13,
    color: theme.colors.ink,
  },
  resBtnAlt: {
    flex: 1,
    flexDirection: "row",
    gap: theme.spacing2.sm,
    height: 48,
    borderRadius: theme.radius.pill,
    borderWidth: 1.5,
    borderColor: theme.colors.brandDark,
    alignItems: "center",
    justifyContent: "center",
  },
  resBtnAltText: {
    fontFamily: theme.typography.fontFamily.bold,
    fontSize: 14,
    color: theme.colors.brandDark,
  },
});
