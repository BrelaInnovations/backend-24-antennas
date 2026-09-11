import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import React, { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextStyle,
  View,
  ViewStyle,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import AnimatedPet from "../../components/common/AnimatedPet";
import Dome3D from "../../components/common/Dome3D";
import { api } from "../../utils/api";
// import { useApp } from "@/src/lib/AppContext";
import { useAppTheme } from "../../theme/ThemeProvider";
import { useAuthStore } from "../../store/authStore";
import { UserStackParamList } from "../../navigation/types";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useFocusEffect } from "@react-navigation/native";
import { ScreenWrapper } from "../../components/layout/ScreenWrapper";
import { MOOD_META, PETS } from "../common/AvatarScreen";

type HomeScreenProps = NativeStackScreenProps<UserStackParamList, "UserHome">;

export const HomeScreen: React.FC<HomeScreenProps> = ({ navigation }) => {
  const { theme } = useAppTheme();
  const { userProfile } = useAuthStore();

  const insets = useSafeAreaInsets();
  //   const { user } = useApp();
  const [scan, setScan] = useState<any>(null);
  const [cycle, setCycle] = useState<any>(null);
  const [avatar, setAvatar] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [testing, setTesting] = useState(false);

  const displayName = userProfile?.firstName || "User";

  const dynamicStyles = useMemo(
    () => ({
      root: { backgroundColor: theme.colors.surface },
      header: {
        flexDirection: "row",
        justifyContent: "space-between",
        alignItems: "center",
        paddingHorizontal: theme.spacing2.lg,
        marginBottom: theme.spacing2.md,
      } as TextStyle,
      logo: {
        fontFamily: theme.typography.fontFamily.xbold,
        fontSize: 26,
        color: theme.colors.brandDark,
        letterSpacing: 0.5,
      } as TextStyle,
      greeting: {
        fontFamily: theme.typography.fontFamily.reg,
        fontSize: 14,
        color: theme.colors.inkSoft,
        marginTop: 2,
      } as TextStyle,
      avatarBtn: {
        width: 44,
        height: 44,
        borderRadius: 22,
        backgroundColor: theme.colors.surfaceContainer,
        alignItems: "center",
        justifyContent: "center",
        borderWidth: 1,
        borderColor: theme.colors.border,
      } as ViewStyle,
      petWidget: { alignItems: "center", maxWidth: 86 } as ViewStyle,
      petWidgetName: {
        fontFamily: theme.typography.fontFamily.xbold,
        fontSize: 10,
        color: theme.colors.brandDark,
        backgroundColor: "#FFFFFFD0",
        paddingHorizontal: 8,
        paddingVertical: 2,
        borderRadius: theme.radius.pill,
        marginTop: -6,
        overflow: "hidden",
      } as TextStyle,
      alertBanner: {
        flexDirection: "row",
        alignItems: "center",
        gap: theme.spacing2.sm,
        marginHorizontal: theme.spacing2.lg,
        marginBottom: theme.spacing2.md,
        padding: theme.spacing2.md,
        borderRadius: theme.radius.lg,
      } as ViewStyle,
      alertText: {
        flex: 1,
        fontFamily: theme.typography.fontFamily.bold,
        fontSize: 13,
        color: "#fff",
      } as TextStyle,
      hero: {
        flexDirection: "row",
        marginTop: 0,
        marginHorizontal: theme.spacing2.lg,
        borderRadius: theme.radius.lg,
        padding: theme.spacing2.xl,
        ...theme.shadow.card,
      } as ViewStyle,
      heroLabel: {
        fontFamily: theme.typography.fontFamily.bold,
        fontSize: 13,
        color: theme.colors.inkSoft,
      } as TextStyle,
      heroScore: {
        fontFamily: theme.typography.fontFamily.xbold,
        fontSize: 56,
        color: theme.colors.ink,
        lineHeight: 62,
      } as TextStyle,
      verdictPill: {
        alignSelf: "flex-start",
        paddingHorizontal: theme.spacing2.md,
        paddingVertical: 5,
        borderRadius: theme.radius.pill,
      } as ViewStyle,
      verdictText: {
        fontFamily: theme.typography.fontFamily.xbold,
        fontSize: 12,
        color: "#1F3A34",
      } as TextStyle,
      heroDate: {
        fontFamily: theme.typography.fontFamily.reg,
        fontSize: 12,
        color: theme.colors.inkFaint,
        marginTop: theme.spacing2.sm,
      } as TextStyle,
      sideScores: {
        gap: theme.spacing2.sm,
        justifyContent: "center",
        flex: 1,
      } as ViewStyle,
      sideScore: {
        backgroundColor: "#FFFFFFB0",
        borderRadius: theme.radius.md,
        paddingVertical: theme.spacing2.sm,
        paddingHorizontal: theme.spacing2.lg,
        alignItems: "center",
      } as ViewStyle,
      sideScoreNum: {
        fontFamily: theme.typography.fontFamily.xbold,
        fontSize: 20,
        color: theme.colors.ink,
      } as TextStyle,
      sideScoreLabel: {
        fontFamily: theme.typography.fontFamily.reg,
        fontSize: 11,
        color: theme.colors.inkSoft,
      } as TextStyle,
      sectionTitle: {
        fontFamily: theme.typography.fontFamily.xbold,
        fontSize: 16,
        color: theme.colors.ink,
        marginHorizontal: theme.spacing2.lg,
        marginTop: theme.spacing2.xl,
        marginBottom: theme.spacing2.md,
      } as TextStyle,
      domesRow: {
        flexDirection: "row",
        gap: theme.spacing2.md,
        paddingHorizontal: theme.spacing2.lg,
      } as ViewStyle,
      domeCard: {
        flex: 1,
        backgroundColor: theme.colors.surfaceContainerLow,
        borderRadius: theme.radius.lg,
        alignItems: "center",
        paddingVertical: theme.spacing2.sm,
        borderWidth: 1,
        borderColor: theme.colors.border,
        ...theme.shadow.card,
      } as ViewStyle,
      domeOpenBtn: {
        flexDirection: "row",
        alignItems: "center",
        gap: 4,
        paddingVertical: 6,
        paddingHorizontal: theme.spacing2.md,
        backgroundColor: theme.colors.surfaceContainer,
        borderRadius: theme.radius.pill,
      } as ViewStyle,
      domeOpenText: {
        fontFamily: theme.typography.fontFamily.bold,
        fontSize: 12,
        color: theme.colors.brandDark,
      } as TextStyle,
      emptyCard: {
        alignItems: "center",
        marginHorizontal: theme.spacing2.lg,
        backgroundColor: theme.colors.surfaceContainerLow,
        borderRadius: theme.radius.lg,
        padding: theme.spacing2.xxl,
        borderWidth: 1,
        borderColor: theme.colors.border,
      } as ViewStyle,
      emptyTitle: {
        fontFamily: theme.typography.fontFamily.xbold,
        fontSize: 17,
        color: theme.colors.ink,
        marginTop: theme.spacing2.sm,
      } as TextStyle,
      emptySub: {
        fontFamily: theme.typography.fontFamily.reg,
        fontSize: 13,
        color: theme.colors.inkSoft,
        textAlign: "center",
        marginTop: 4,
      } as ViewStyle,
      actionsGrid: {
        flexDirection: "row",
        flexWrap: "wrap",
        gap: theme.spacing2.md,
        paddingHorizontal: theme.spacing2.lg,
      } as ViewStyle,
      action: {
        width: "47%",
        flexGrow: 1,
        borderRadius: theme.radius.lg,
        padding: theme.spacing2.lg,
        gap: 4,
      } as ViewStyle,
      actionIcon: {
        width: 48,
        height: 48,
        borderRadius: 24,
        backgroundColor: "#FFFFFFCC",
        alignItems: "center",
        justifyContent: "center",
        marginBottom: 4,
      } as ViewStyle,
      actionLabel: {
        fontFamily: theme.typography.fontFamily.xbold,
        fontSize: 15,
        color: theme.colors.ink,
      } as TextStyle,
      actionSub: {
        fontFamily: theme.typography.fontFamily.reg,
        fontSize: 11,
        color: theme.colors.inkSoft,
      } as TextStyle,
      testCard: {
        marginHorizontal: theme.spacing2.lg,
        marginTop: theme.spacing2.md,
        backgroundColor: theme.colors.surfaceContainerLow,
        borderRadius: theme.radius.lg,
        padding: theme.spacing2.lg,
        borderWidth: 1,
        borderColor: theme.colors.border,
      } as ViewStyle,
      testHeader: {
        flexDirection: "row",
        alignItems: "center",
        gap: theme.spacing2.sm,
      } as ViewStyle,
      testTitle: {
        flex: 1,
        fontFamily: theme.typography.fontFamily.bold,
        fontSize: 14,
        color: theme.colors.ink,
      } as TextStyle,
      testGrid: {
        flexDirection: "row",
        flexWrap: "wrap",
        gap: 5,
        marginTop: theme.spacing2.md,
      } as ViewStyle,
      testDot: { width: 14, height: 14, borderRadius: 4 } as ViewStyle,
      testSub: {
        fontFamily: theme.typography.fontFamily.reg,
        fontSize: 12,
        color: theme.colors.inkSoft,
        marginTop: theme.spacing2.sm,
      } as TextStyle,
      testFail: {
        fontFamily: theme.typography.fontFamily.bold,
        fontSize: 13,
        color: theme.colors.error,
      } as TextStyle,
      ctaWrap: {
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 0,
        paddingHorizontal: theme.spacing2.lg,
        paddingTop: theme.spacing2.sm,
      } as ViewStyle,
      cta: {
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "center",
        gap: theme.spacing2.sm,
        height: 56,
        borderRadius: theme.radius.pill,
        ...theme.shadow.card,
      } as ViewStyle,
      ctaText: {
        fontFamily: theme.typography.fontFamily.xbold,
        fontSize: 17,
        color: "#fff",
      } as TextStyle,
    }),
    [theme],
  );

  const load = useCallback(async () => {
    try {
      const [cy, av] = await Promise.all([
        api.cycleStatus(),
        api.avatarStatus(),
      ]);
      setCycle(cy);
      setAvatar(av);
      try {
        setScan(await api.latestScan());
      } catch {
        setScan(null);
      }
    } catch (e) {
      console.log("home load", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const runPairTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await api.antennaTest());
    } catch (e: any) {
      setTestResult({ error: e.message });
    } finally {
      setTesting(false);
    }
  };

  // Handle cases where metrics might be null (single dome or incomplete scan)
  const hasMetrics = scan?.metrics != null;
  const isSingleDome =
    !hasMetrics || (scan?.left && !scan?.right) || (!scan?.left && scan?.right);
  const displayScore = hasMetrics
    ? scan.metrics.overall_score
    : scan?.left?.score || scan?.right?.score || 0;
  const displayVerdict = hasMetrics
    ? scan.metrics.verdict_label
    : displayScore >= 80
      ? "Healthy"
      : displayScore >= 60
        ? "Monitor"
        : "Pending";

  const verdictColor = theme.colors.brandDark;

  const pet = PETS.find((p) => p.key === (userProfile?.avatar_type || "kitten")) || PETS[0];
  const petSize = 120 + (avatar?.stage || 0) * 20;

  function ActionCard({
    icon,
    label,
    sub,
    color,
    iconColor,
    onPress,
    loading,
    testID,
    indicatorColor,
  }: any) {
    return (
      <Pressable
        testID={testID}
        style={[dynamicStyles.action, { backgroundColor: color }]}
        onPress={onPress}
      >
        <View style={dynamicStyles.actionIcon}>
          {loading ? (
            <ActivityIndicator color={indicatorColor} size="small" />
          ) : (
            <Ionicons name={icon} size={26} color={iconColor} />
          )}
        </View>
        <Text style={dynamicStyles.actionLabel}>{label}</Text>
        <Text style={dynamicStyles.actionSub}>{sub}</Text>
      </Pressable>
    );
  }

  return (
    <ScreenWrapper
      contentContainerStyle={dynamicStyles.root}
      scrollable={true}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => {
            setRefreshing(true);
            //  load();
          }}
          tintColor={theme.colors.onSurface}
        />
      }
      floatingContent={
        <View style={dynamicStyles.ctaWrap} >
          <View style={{
            alignSelf: 'flex-end',
            zIndex: 10,
          }}>
            <AnimatedPet
              type={pet.key}
              mood={avatar?.mood || "waiting"}
              level={[1, 5, 10, 15, 20][avatar?.stage] ?? 1}
              size={petSize}
              testID="avatar-pet"
            />
          </View>
          <View
            style={[{ paddingBottom: theme.spacing2.lg }]}
          >
            <Pressable
              testID="home-start-scan-button"
              onPress={() => navigation.navigate("Scan")}
            >
              <LinearGradient
                colors={[...theme.GradColors.cta]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 0 }}
                style={dynamicStyles.cta}
              >
                <Ionicons name="radio-outline" size={26} color="#fff" />
                <Text style={dynamicStyles.ctaText}>Start 1-Min Scan</Text>
              </LinearGradient>
            </Pressable>
          </View>
        </View>
      }
    >
      {/* Header */}
      {/* <View style={styles.header}>
          <View>
            <Text style={styles.logo}>ovula ✿</Text>
            <Text style={styles.greeting}>Hi {user?.name?.trim() ? user.name : "lovely"} 🌸</Text>
          </View>
          <Pressable testID="home-avatar-button" style={styles.petWidget} onPress={() => router.push("/avatar")}>
            <AnimatedPet type={(user as any)?.avatar_type || "kitten"} mood={avatar?.mood || "happy"} size={56} interactive={false} />
            <Text style={styles.petWidgetName} numberOfLines={1}>
              {(user as any)?.companion_name?.trim() || "Companion"}
            </Text>
          </Pressable>
        </View> */}

      {/* Day 3 alert */}
      {cycle?.is_test_day && (
        <Pressable
          testID="home-day3-alert"
          onPress={() => navigation.push("Scan")}
        >
          <LinearGradient
            colors={[theme.colors.brand, theme.colors.lavenderDark]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={dynamicStyles.alertBanner}
          >
            <Ionicons name="notifications" size={20} color="#fff" />
            <Text style={dynamicStyles.alertText}>
              It&apos;s Day 3 of your cycle — time for your 1-minute test! ✨
            </Text>
            <Ionicons name="chevron-forward" size={18} color="#fff" />
          </LinearGradient>
        </Pressable>
      )}

      {loading ? (
        <ActivityIndicator
          color={theme.colors.brandDark}
          style={{ marginTop: 60 }}
          size="large"
        />
      ) : scan ? (
        <>
          {/* Score hero */}
          <LinearGradient
            colors={["#FDE7F1", "#EDE4FC", "#E3ECFD"]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={dynamicStyles.hero}
          >
            <View style={{ flex: 1 }}>
              <Text style={dynamicStyles.heroLabel}>
                DMAS-CF displayed locations
              </Text>
              <Text testID="home-overall-score" style={dynamicStyles.heroScore}>
                {scan?.left?.dot_count ?? scan?.right?.dot_count ?? "—"}
              </Text>
              <View
                style={[
                  dynamicStyles.verdictPill,
                  { backgroundColor: verdictColor },
                ]}
              >
                <Text testID="home-verdict" style={dynamicStyles.verdictText}>
                  {scan?.display_mode === "localization" ? displayVerdict : "Legacy scan"}
                </Text>
              </View>
              <Text style={dynamicStyles.heroDate}>
                Last scan ·{" "}
                {new Date(scan.created_at).toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric",
                })}
              </Text>
            </View>
            <View style={{ alignItems: "center" }}>
              <View style={dynamicStyles.sideScores}>
                {scan?.left && (
                  <View style={dynamicStyles.sideScore}>
                    <Text style={dynamicStyles.sideScoreNum}>
                      {scan.left.dot_count ?? "—"}
                    </Text>
                    <Text style={dynamicStyles.sideScoreLabel}>Left</Text>
                  </View>
                )}
                {scan?.right && (
                  <View style={dynamicStyles.sideScore}>
                    <Text style={dynamicStyles.sideScoreNum}>
                      {scan.right.dot_count ?? "—"}
                    </Text>
                    <Text style={dynamicStyles.sideScoreLabel}>Right</Text>
                  </View>
                )}
              </View>
            </View>
          </LinearGradient>

          {/* Interactive mini domes */}
          <Text style={dynamicStyles.sectionTitle}>
            {isSingleDome
              ? `${scan?.left ? "Left" : "Right"} breast profile`
              : "Latest breast profiles"}
          </Text>
          <View
            style={[
              dynamicStyles.domesRow,
              isSingleDome && { justifyContent: "center" },
            ]}
          >
            {(() => {
              const availableSides: Array<"left" | "right"> = [];
              if (scan?.left?.dots) availableSides.push("left");
              if (scan?.right?.dots) availableSides.push("right");

              return availableSides.map((side) => (
                <Pressable
                  key={side}
                  style={[
                    dynamicStyles.domeCard,
                    isSingleDome && { maxWidth: 200, alignSelf: "center" },
                  ]}
                  testID={`home-dome-card-${side}`}
                  onPress={() =>
                    navigation.navigate("Dome", { scanId: scan.id, side })
                  }
                >
                  <Dome3D
                    size={isSingleDome ? 180 : 150}
                    dots={scan[side]?.dots || []}
                    antennas={scan.antennas || []}
                    showAntennas={false}
                    testID={`home-dome-${side}`}
                  />
                  <Pressable
                    testID={`home-dome-${side}-open`}
                    style={dynamicStyles.domeOpenBtn}
                    onPress={() =>
                      navigation.navigate("Dome", { scanId: scan.id, side })
                    }
                  >
                    <Text style={dynamicStyles.domeOpenText}>
                      {side === "left" ? "Left" : "Right"} · explore
                    </Text>
                    <Ionicons
                      name="expand-outline"
                      size={13}
                      color={theme.colors.brandDark}
                    />
                  </Pressable>
                </Pressable>
              ));
            })()}
          </View>
        </>
      ) : (
        <View style={dynamicStyles.emptyCard}>
          <Ionicons
            name="flower-outline"
            size={44}
            color={theme.colors.brand}
          />
          <Text style={dynamicStyles.emptyTitle}>No scans yet</Text>
          <Text style={dynamicStyles.emptySub}>
            Run your first 1-minute scan to build your breast profile 💗
          </Text>
        </View>
      )}

      {/* Quick actions */}
      <Text style={dynamicStyles.sectionTitle}>Quick actions</Text>
      <View style={dynamicStyles.actionsGrid}>
        <ActionCard
          testID="home-pair-test-button"
          icon="wifi"
          iconColor={theme.colors.lavenderDark}
          label="Pair & Test"
          sub="Antenna check"
          color="#EFE4FF"
          indicatorColor={theme.colors.brandDark}
          onPress={runPairTest}
          loading={testing}
        />
        <ActionCard
          testID="home-log-period-button"
          icon="water"
          iconColor={theme.colors.brandDark}
          indicatorColor={theme.colors.brandDark}

          label="Log Period"
          sub="Cycle calendar"
          color="#FFE0EE"
          onPress={() => navigation.navigate("Calendar")}
        />
        <ActionCard
          testID="home-compare-button"
          icon="git-compare"
          iconColor={theme.colors.blueDark}
          indicatorColor={theme.colors.brandDark}

          label="Compare"
          sub="Two profiles"
          color="#DFE9FF"
          onPress={() =>
            navigation.navigate("Repository", {
              screen: "Scans",
              params: {
                compare: "1",
              },
            })
          }
        />
        <ActionCard
          testID="home-repository-button"
          icon="albums"
          iconColor="#2FA98C"
          label="Repository"
          sub="All profiles"
          color="#DDF6EE"
          indicatorColor={theme.colors.brandDark}

          onPress={() => navigation.navigate("Repository")}
        />
      </View>

      {/* Pair test result */}
      {testResult && (
        <View testID="home-pair-test-result" style={dynamicStyles.testCard}>
          {testResult.error ? (
            <Text style={dynamicStyles.testFail}>
              Test failed: {testResult.error}
            </Text>
          ) : (
            <>
              <View style={dynamicStyles.testHeader}>
                <Ionicons
                  name={testResult.all_ok ? "checkmark-circle" : "warning"}
                  size={22}
                  color={
                    testResult.all_ok
                      ? theme.colors.success
                      : theme.colors.warning
                  }
                />
                <Text style={dynamicStyles.testTitle}>
                  {testResult.responding ?? 0}/{testResult.total_enabled ?? 0}{" "}
                  antennas responding
                </Text>
                <Pressable
                  onPress={() => setTestResult(null)}
                  testID="home-pair-test-close"
                >
                  <Ionicons
                    name="close"
                    size={18}
                    color={theme.colors.inkFaint}
                  />
                </Pressable>
              </View>
              <View style={dynamicStyles.testGrid}>
                {testResult.results?.map((r: any) => (
                  <View
                    key={r.id}
                    style={[
                      dynamicStyles.testDot,
                      {
                        backgroundColor: !r.enabled
                          ? theme.colors.border
                          : r.responding
                            ? theme.colors.success
                            : theme.colors.error,
                      },
                    ]}
                  />
                ))}
              </View>
              <Text style={dynamicStyles.testSub}>
                {testResult.all_ok
                  ? "All systems go — NanoVNA + switch matrix OK ✨"
                  : "Some antennas silent — re-seat the patch or check the Lab tab."}
              </Text>
            </>
          )}
        </View>
      )}
    </ScreenWrapper>
  );
};
