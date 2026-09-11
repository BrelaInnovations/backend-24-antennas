import { Ionicons } from "@expo/vector-icons";
import dayjs from "dayjs";
import React, { useCallback, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useFocusEffect } from "@react-navigation/native";
import { NativeStackScreenProps } from "@react-navigation/native-stack";

import { ScreenWrapper } from "../../components/layout/ScreenWrapper";
import { SectionHeader } from "../../components/common/SectionHeader";
import { UserStackParamList } from "../../navigation/types";
import { useAppTheme } from "../../theme/ThemeProvider";
import { api } from "../../utils/api";
import AppBottomSheet from "../../components/common/AppBottomSheet";

type Props = NativeStackScreenProps<UserStackParamList, "Scans">;

type ScanItem = {
  id: string;
  label: string;
  created_at: string;
  left_dot_count?: number;
  right_dot_count?: number;
  display_mode?: string;
  left_score: number;
  right_score: number;
  asymmetry: number;
  overall_score: number;
  verdict: string;
  verdict_label: string;
  scanned_side?: "left" | "right" | "both";
  config_snapshot?: any;
};

export const RepositoryScreen: React.FC<Props> = ({ navigation, route }) => {
  const { theme } = useAppTheme();
  const insets = useSafeAreaInsets();
  const { params } = route;

  const [scans, setScans] = useState<ScanItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [selectMode, setSelectMode] = useState(
    Boolean(params?.compare === "1"),
  );

  const [editingScan, setEditingScan] = useState<ScanItem | null>(null);
  const [editingText, setEditingText] = useState("");
  const [showEditSheet, setShowEditSheet] = useState(false);

  const load = useCallback(async (isRefreshing = false) => {
    try {
      if (isRefreshing) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      const nextScans = await api.listScans();
      setScans(nextScans);
    } catch (error) {
      console.log("Repository load error", error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const toggleSelect = useCallback((id: string) => {
    setSelected((prev) => {
      if (prev.includes(id)) {
        return prev.filter((itemId) => itemId !== id);
      }

      if (prev.length >= 2) {
        return [prev[1], id];
      }

      return [...prev, id];
    });
  }, []);

  const handleDelete = useCallback(
    async (id: string) => {
      try {
        await api.deleteScan(id);
        setSelected((prev) => prev.filter((itemId) => itemId !== id));
        await load();
      } catch (error) {
        console.log("Delete scan error", error);
      }
    },
    [load],
  );
  const handleStartEdit = useCallback((scan: ScanItem) => {
    setEditingScan(scan);

    setEditingText(
      scan.label || dayjs(scan.created_at).format("MMM D, YYYY · h:mm A"),
    );
    setShowEditSheet(true);
  }, []);

  const handleSaveLabel = useCallback(async () => {
    if (!editingScan) return;

    try {
      const updated = await api.updateScanLabel(editingScan.id, editingText);

      setScans((prev) =>
        prev.map((s) =>
          s.id === editingScan.id ? { ...s, label: updated.label } : s,
        ),
      );

      setShowEditSheet(false);
      setEditingScan(null);
    } catch (error) {
      console.log(error);
    }
  }, [editingScan, editingText]);

  const handleToggleSelectMode = useCallback(() => {
    setSelectMode((prev) => !prev);
    setSelected([]);
  }, []);

  const handleRefresh = useCallback(() => {
    void load(true);
  }, [load]);

  const verdictColor = useCallback(
    (value: string) =>
      value === "healthy"
        ? theme.colors.success
        : value === "monitor"
          ? theme.colors.warning
          : theme.colors.error,
    [theme.colors.error, theme.colors.success, theme.colors.warning],
  );

  const styles = useMemo(
    () =>
      StyleSheet.create({
        headerRow: {
          flexDirection: "row",
          justifyContent: "flex-end",
          alignItems: "center",
        },
        compareToggle: {
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "center",
          gap: 6,
          height: 36,
          paddingHorizontal: theme.spacing2.md,
          borderRadius: theme.radius.pill,
          borderWidth: 1.5,
          borderColor: theme.colors.brandDark,
        },
        compareToggleText: {
          fontFamily: theme.typography.fontFamily.bold,
          fontSize: 12,
          color: theme.colors.brandDark,
        },
        selectHint: {
          fontFamily: theme.typography.fontFamily.reg,
          fontSize: 12,
          color: theme.colors.inkSoft,
          paddingHorizontal: theme.spacing2.lg,
          marginTop: 4,
          marginBottom: theme.spacing2.sm,
        },
        list: {
          flex: 1,
        },
        listContent: {
          // paddingHorizontal: theme.spacing2.md,
          paddingTop: theme.spacing2.sm,
          paddingBottom: insets.bottom + 120,
        },
        card: {
          flexDirection: "row",
          alignItems: "center",
          gap: theme.spacing2.md,
          marginBottom: theme.spacing2.md,
          backgroundColor: theme.colors.surface2,
          borderRadius: theme.radius.lg,
          padding: theme.spacing2.lg,
          borderWidth: 1,
          borderColor: theme.colors.border,
          ...theme.shadow.card,
        },
        cardSel: { borderColor: theme.colors.brandDark, borderWidth: 2 },
        checkbox: {
          width: 22,
          height: 22,
          borderRadius: 11,
          borderWidth: 2,
          borderColor: theme.colors.borderStrong,
          alignItems: "center",
          justifyContent: "center",
        },
        cardMain: {
          flex: 1,
          minWidth: 0,
        },
        titleRow: {
          flexDirection: "row",
          alignItems: "center",
          gap: 6,
        },
        editTitleRow: {
          flexDirection: "row",
          alignItems: "center",
          gap: 6,
          marginBottom: 2,
        },
        editTitleInput: {
          flex: 1,
          fontFamily: theme.typography.fontFamily.bold,
          fontSize: 14,
          color: theme.colors.ink,
          backgroundColor: theme.colors.surface,
          borderRadius: theme.radius.sm,
          paddingHorizontal: 8,
          paddingVertical: 3,
          borderWidth: 1,
          borderColor: theme.colors.brandDark,
        },
        editActionBtn: {
          padding: 2,
        },
        editPencilBtn: {
          padding: 2,
        },
        cardTitle: {
          fontFamily: theme.typography.fontFamily.xbold,
          fontSize: 14,
          color: theme.colors.ink,
          flexShrink: 1,
        },
        cardDate: {
          fontFamily: theme.typography.fontFamily.reg,
          fontSize: 11,
          color: theme.colors.inkFaint,
          marginTop: 2,
        },
        scoreRow: {
          flexDirection: "row",
          flexWrap: "wrap",
          gap: 6,
          marginTop: theme.spacing2.sm,
        },
        scoreChip: {
          backgroundColor: theme.colors.surface3,
          borderRadius: theme.radius.pill,
          paddingHorizontal: theme.spacing2.sm,
          paddingVertical: 3,
        },
        scoreChipText: {
          fontFamily: theme.typography.fontFamily.bold,
          fontSize: 11,
          color: theme.colors.inkSoft,
        },
        sideChip: {
          backgroundColor: theme.colors.brandDark,
        },
        configRow: {
          marginTop: theme.spacing2.sm,
        },
        configText: {
          fontFamily: theme.typography.fontFamily.reg,
          fontSize: 10,
          color: theme.colors.inkFaint,
        },
        cardMeta: {
          alignItems: "flex-end",
          gap: 6,
        },
        bigScore: {
          fontFamily: theme.typography.fontFamily.xbold,
          fontSize: 24,
          color: theme.colors.ink,
        },
        verdictPill: {
          paddingHorizontal: theme.spacing2.sm,
          paddingVertical: 3,
          borderRadius: theme.radius.pill,
        },
        verdictText: {
          fontFamily: theme.typography.fontFamily.bold,
          fontSize: 10,
          color: "#1F3A34",
        },
        empty: {
          alignItems: "center",
          justifyContent: "center",
          minHeight: 280,
          paddingHorizontal: theme.spacing2.xl,
        },
        emptyTitle: {
          fontFamily: theme.typography.fontFamily.xbold,
          fontSize: 16,
          color: theme.colors.ink,
          marginTop: theme.spacing2.sm,
        },
        emptySub: {
          fontFamily: theme.typography.fontFamily.reg,
          fontSize: 13,
          color: theme.colors.inkSoft,
          textAlign: "center",
          marginTop: 4,
        },
        emptyBtn: {
          marginTop: theme.spacing2.lg,
          height: 44,
          paddingHorizontal: theme.spacing2.xl,
          borderRadius: theme.radius.pill,
          backgroundColor: theme.colors.brandDark,
          alignItems: "center",
          justifyContent: "center",
        },
        emptyBtnText: {
          fontFamily: theme.typography.fontFamily.xbold,
          fontSize: 14,
          color: "#fff",
        },
        compareBar: {
          position: "absolute",
          left: theme.spacing2.lg,
          right: theme.spacing2.lg,
          bottom: insets.bottom + theme.spacing2.lg,
        },
        compareBtn: {
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "center",
          gap: theme.spacing2.sm,
          height: 52,
          borderRadius: theme.radius.pill,
          backgroundColor: theme.colors.brandDark,
          ...theme.shadow.card,
        },
        compareBtnText: {
          fontFamily: theme.typography.fontFamily.xbold,
          fontSize: 15,
          color: "#fff",
        },
      }),
    [insets.bottom, theme],
  );

  const renderItem = useCallback(
    ({ item }: { item: ScanItem }) => {
      const isSelected = selected.includes(item.id);

      return (
        <Pressable
          testID={`repo-scan-${item.id}`}
          style={[styles.card, isSelected && styles.cardSel]}
          onPress={() => {
            if (selectMode) {
              toggleSelect(item.id);
            } else {
              navigation.push("Dome", { scanId: item.id });
            }
          }}
          android_ripple={{ color: theme.colors.surface3 }}
        >
          {selectMode && (
            <View
              style={[
                styles.checkbox,
                isSelected && {
                  backgroundColor: theme.colors.brandDark,
                  borderColor: theme.colors.brandDark,
                },
              ]}
            >
              {isSelected && (
                <Ionicons name="checkmark" size={14} color="#fff" />
              )}
            </View>
          )}

          <View style={styles.cardMain}>
            <Pressable onPress={() => handleStartEdit(item)}>
              <View style={styles.titleRow}>
                <Text style={styles.cardTitle}>
                  {item.label ||
                    dayjs(item.created_at).format("MMM D, YYYY · h:mm A")}
                </Text>

                {!selectMode && (
                  <Ionicons
                    name="create-outline"
                    size={15}
                    color={theme.colors.brandDark}
                  />
                )}
              </View>
            </Pressable>
            <Text style={styles.cardDate}>
              {dayjs(item.created_at).format("MMM D, YYYY · h:mm A")}
            </Text>
            <View style={styles.scoreRow}>
              <View style={styles.scoreChip}>
                <Text style={styles.scoreChipText}>L {item.left_dot_count ?? "—"} locations</Text>
              </View>
              <View style={styles.scoreChip}>
                <Text style={styles.scoreChipText}>R {item.right_dot_count ?? "—"} locations</Text>
              </View>
              <View style={styles.scoreChip}>
                <Text style={styles.scoreChipText}>{item.display_mode === "localization" ? "DMAS-CF" : "Legacy"}</Text>
              </View>
              {item.scanned_side && (
                <View style={[styles.scoreChip, styles.sideChip]}>
                  <Text style={styles.scoreChipText}>
                    {item.scanned_side === "left"
                      ? "Left"
                      : item.scanned_side === "right"
                        ? "Right"
                        : "Both"}
                  </Text>
                </View>
              )}
            </View>

            {item.config_snapshot && (
              <View style={styles.configRow}>
                <Text style={styles.configText}>
                  {item.config_snapshot.num_prongs}×
                  {item.config_snapshot.antennas_per_prong} ·{" "}
                  {item.config_snapshot.freq_start_mhz / 1000}-
                  {item.config_snapshot.freq_stop_mhz / 1000}GHz
                </Text>
              </View>
            )}
          </View>

          <View style={styles.cardMeta}>
            <Text style={styles.bigScore}>{item.left_dot_count ?? "—"}</Text>
            <View
              style={[
                styles.verdictPill,
                { backgroundColor: verdictColor(item.verdict) },
              ]}
            >
              <Text style={styles.verdictText}>{item.display_mode === "localization" ? item.verdict_label : "Legacy scan"}</Text>
            </View>

            {!selectMode && (
              <Pressable
                testID={`repo-delete-${item.id}`}
                onPress={() => void handleDelete(item.id)}
                hitSlop={8}
              >
                <Ionicons
                  name="trash-outline"
                  size={16}
                  color={theme.colors.inkFaint}
                />
              </Pressable>
            )}
          </View>
        </Pressable>
      );
    },
    [
      handleDelete,
      handleStartEdit,
      navigation,
      selectMode,
      selected,
      styles,
      theme.colors.brandDark,
      theme.colors.error,
      theme.colors.inkFaint,
      theme.colors.success,
      theme.colors.surface3,
      toggleSelect,
      verdictColor,
    ],
  );

  return (
    <ScreenWrapper hideHeader={true} scrollable={false}>
      <SectionHeader
        title="Profile Repository"
        rightAction={
          <Pressable
            testID="repo-select-mode-button"
            style={[
              styles.compareToggle,
              selectMode && { backgroundColor: theme.colors.brandDark },
            ]}
            onPress={handleToggleSelectMode}
          >
            <Ionicons
              name="git-compare"
              size={16}
              color={selectMode ? "#fff" : theme.colors.brandDark}
            />
            <Text
              style={[
                styles.compareToggleText,
                selectMode && { color: "#fff" },
              ]}
            >
              Compare
            </Text>
          </Pressable>
        }
      />

      {selectMode && (
        <Text style={styles.selectHint}>
          Select two profiles to compare ({selected.length}/2)
        </Text>
      )}

      {loading ? (
        <ActivityIndicator
          size="large"
          color={theme.colors.brandDark}
          style={{ marginTop: 60 }}
        />
      ) : (
        <FlatList
          data={scans}
          keyExtractor={(item) => item.id}
          style={styles.list}
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={handleRefresh}
              tintColor={theme.colors.brandDark}
            />
          }
          ListEmptyComponent={
            <View style={styles.empty}>
              <Ionicons
                name="albums-outline"
                size={40}
                color={theme.colors.brand}
              />
              <Text style={styles.emptyTitle}>No profiles yet</Text>
              <Text style={styles.emptySub}>
                Every scan is saved here so you can compare over time.
              </Text>
              <Pressable
                testID="repo-first-scan-button"
                style={styles.emptyBtn}
              >
                <Text style={styles.emptyBtnText}>Run first scan</Text>
              </Pressable>
            </View>
          }
          renderItem={renderItem}
        />
      )}

      {selectMode && selected.length === 2 && (
        <View style={styles.compareBar}>
          <Pressable
            testID="repo-compare-button"
            style={styles.compareBtn}
            onPress={() =>
              navigation.navigate("Compare", {
                a: selected[0],
                b: selected[1],
              })
            }
          >
            <Ionicons name="git-compare" size={18} color="#fff" />
            <Text style={styles.compareBtnText}>Compare selected profiles</Text>
          </Pressable>
        </View>
      )}
      <AppBottomSheet
        isVisible={showEditSheet}
        onClose={() => {
          setShowEditSheet(false);
          setEditingScan(null);
        }}
        snapPoints={["85%"]}
        title="Rename profile"
      >
        <View style={{ padding: 20 }}>
          <TextInput
            value={editingText}
            onChangeText={setEditingText}
            onSubmitEditing={handleSaveLabel} // Handles the Enter key
            returnKeyType="done"
            autoFocus
            style={{
              borderWidth: 1,
              borderColor: theme.colors.border,
              borderRadius: 12,
              padding: 12,
              color: theme.colors.ink,
            }}
          />

          <Pressable
            onPress={handleSaveLabel}
            style={{
              marginTop: 20,
              height: 48,
              borderRadius: 24,
              backgroundColor: theme.colors.brandDark,
              justifyContent: "center",
              alignItems: "center",
            }}
          >
            <Text
              style={{
                color: "#fff",
                fontWeight: "700",
              }}
            >
              Save
            </Text>
          </Pressable>
        </View>
      </AppBottomSheet>
    </ScreenWrapper>
  );
};
