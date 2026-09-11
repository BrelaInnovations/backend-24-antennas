import { Ionicons } from "@expo/vector-icons";
import dayjs from "dayjs";
import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Dome3D from "../../components/common/Dome3D";
import { api } from "../../utils/api";
import { theme } from "../../theme";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { UserStackParamList } from "../../navigation/types";
import { ScreenWrapper } from "../../components/layout/ScreenWrapper";

type Props = NativeStackScreenProps<UserStackParamList, "Compare">;

export const CompareScreen: React.FC<Props> = ({ navigation, route }) => {
  const { a, b } = route.params;
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [side, setSide] = useState<"left" | "right">("left");

  useEffect(() => {
    if (a && b)
      api
        .compare(a, b)
        .then(setData)
        .catch((e) => setErr(e.message));
  }, [a, b]);

  const domeSize =
    (width - theme.spacing2.lg * 2 - theme.spacing2.md) / 2 - theme.spacing2.sm;

  const DeltaRow = ({
    label,
    value,
    invert,
  }: {
    label: string;
    value: number;
    invert?: boolean;
  }) => {
    const good = invert ? value < 0 : value > 0;
    const neutral = value === 0;
    return (
      <View style={styles.deltaRow}>
        <Text style={styles.deltaLabel}>{label}</Text>
        <View style={styles.deltaVal}>
          <Ionicons
            name={neutral ? "remove" : value > 0 ? "arrow-up" : "arrow-down"}
            size={14}
            color={
              neutral
                ? theme.colors.inkFaint
                : good
                  ? "#3AA981"
                  : theme.colors.error
            }
          />
          <Text
            style={[
              styles.deltaText,
              {
                color: neutral
                  ? theme.colors.inkFaint
                  : good
                    ? "#3AA981"
                    : theme.colors.error,
              },
            ]}
          >
            {value > 0 ? "+" : ""}
            {value}
          </Text>
        </View>
      </View>
    );
  };

  return (
    <ScreenWrapper hideHeader={true}>
      <View style={styles.header}>
        <Pressable
          testID="compare-back-button"
          style={styles.backBtn}
          onPress={() => navigation.goBack()}
        >
          <Ionicons name="arrow-back" size={22} color={theme.colors.ink} />
        </Pressable>
        <Text style={styles.title}>Compare Profiles</Text>
        <View style={{ width: 40 }} />
      </View>

      {err ? (
        <Text style={styles.errText}>{err}</Text>
      ) : !data ? (
        <ActivityIndicator
          size="large"
          color={theme.colors.brandDark}
          style={{ marginTop: 60 }}
        />
      ) : (
        <ScrollView
          contentContainerStyle={{ paddingBottom: 40 }}
          showsVerticalScrollIndicator={false}
        >
          {/* insight */}
          <View style={styles.insight} testID="compare-insight">
            <Ionicons
              name="analytics"
              size={18}
              color={theme.colors.brandDark}
            />
            <Text style={styles.insightText}>{data.insight}</Text>
          </View>

          {/* side toggle */}
          <View style={styles.segment}>
            {(["left", "right"] as const).map((s) => (
              <Pressable
                key={s}
                testID={`compare-side-${s}`}
                style={[styles.segBtn, side === s && styles.segBtnOn]}
                onPress={() => setSide(s)}
              >
                <Text style={[styles.segText, side === s && styles.segTextOn]}>
                  {s === "left" ? "Left" : "Right"}
                </Text>
              </Pressable>
            ))}
          </View>

          {/* two domes */}
          <View style={styles.domesRow}>
            {[data.a, data.b].map((s: any, i: number) => (
              <View key={s.id} style={styles.domeCard}>
                <Text style={styles.domeLabel}>
                  {i === 0 ? "Earlier" : "Later"}
                </Text>
                <Dome3D
                  size={domeSize}
                  dots={side === "left" ? s.left_dots : s.right_dots}
                  antennas={s.antennas || []}
                  showAntennas={false}
                  testID={`compare-dome-${i === 0 ? "a" : "b"}`}
                />
                <Text style={styles.domeDate}>
                  {dayjs(s.created_at).format("MMM D, YYYY")}
                </Text>
                <Text style={styles.domeScore}>
                  {s.display_mode === "localization" ? s.verdict_label : "Legacy scan"}
                </Text>
              </View>
            ))}
          </View>

          <View style={styles.deltaCard}>
            <Text style={styles.deltaTitle}>DMAS-CF location comparison</Text>
            <Text>{data.insight}</Text>
          </View>
        </ScrollView>
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
    // paddingHorizontal: theme.spacing2.lg,
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
  errText: {
    fontFamily: theme.typography.fontFamily.bold,
    fontSize: 14,
    color: theme.colors.error,
    textAlign: "center",
    marginTop: 60,
  },
  insight: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing2.sm,
    // marginHorizontal: theme.spacing2.lg,
    backgroundColor: "#FDF0F6",
    borderRadius: theme.radius.md,
    padding: theme.spacing2.md,
  },
  insightText: {
    flex: 1,
    fontFamily: theme.typography.fontFamily.bold,
    fontSize: 13,
    color: theme.colors.ink,
  },
  segment: {
    flexDirection: "row",
    // marginHorizontal: theme.spacing2.lg,
    marginTop: theme.spacing2.md,
    backgroundColor: theme.colors.surface3,
    borderRadius: theme.radius.pill,
    padding: 4,
  },
  segBtn: {
    flex: 1,
    height: 36,
    borderRadius: theme.radius.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  segBtnOn: { backgroundColor: theme.colors.brandDark },
  segText: {
    fontFamily: theme.typography.fontFamily.bold,
    fontSize: 13,
    color: theme.colors.inkSoft,
  },
  segTextOn: { color: "#fff" },
  domesRow: {
    flexDirection: "row",
    gap: theme.spacing2.md,
    // paddingHorizontal: theme.spacing2.lg,
    marginTop: theme.spacing2.md,
  },
  domeCard: {
    flex: 1,
    alignItems: "center",
    backgroundColor: theme.colors.surface2,
    borderRadius: theme.radius.lg,
    paddingVertical: theme.spacing2.sm,
    borderWidth: 1,
    borderColor: theme.colors.border,
    ...theme.shadow.card,
  },
  domeLabel: {
    fontFamily: theme.typography.fontFamily.bold,
    fontSize: 11,
    color: theme.colors.inkFaint,
    textTransform: "uppercase",
  },
  domeDate: {
    fontFamily: theme.typography.fontFamily.reg,
    fontSize: 11,
    color: theme.colors.inkSoft,
  },
  domeScore: {
    fontFamily: theme.typography.fontFamily.xbold,
    fontSize: 15,
    color: theme.colors.ink,
    marginBottom: 4,
  },
  deltaCard: {
    // marginHorizontal: theme.spacing2.lg,
    marginTop: theme.spacing2.lg,
    backgroundColor: theme.colors.surface2,
    borderRadius: theme.radius.lg,
    padding: theme.spacing2.lg,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  deltaTitle: {
    fontFamily: theme.typography.fontFamily.xbold,
    fontSize: 14,
    color: theme.colors.ink,
    marginBottom: theme.spacing2.sm,
  },
  deltaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 7,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
  },
  deltaLabel: {
    fontFamily: theme.typography.fontFamily.reg,
    fontSize: 13,
    color: theme.colors.inkSoft,
  },
  deltaVal: { flexDirection: "row", alignItems: "center", gap: 3 },
  deltaText: { fontFamily: theme.typography.fontFamily.xbold, fontSize: 14 },
});
