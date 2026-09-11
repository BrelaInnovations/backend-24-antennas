import { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, {
  useCallback,
  useRef,
  useState,
  useMemo,
  useEffect,
} from "react";
import {
  Animated,
  Dimensions,
  Easing,
  Pressable,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  View,
  ViewStyle,
  TextStyle,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { RootStackParamList } from "../../navigation/types";
import { useAppTheme } from "../../theme/ThemeProvider";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useAuthStore } from "../../store/authStore";

type Props = NativeStackScreenProps<RootStackParamList, "Onboarding">;

const { width: W } = Dimensions.get("window");

const SLIDES = [
  {
    phase: "STEP 01 · MEET YOUR COMPANION",
    phaseNum: "01",
    titlePart1: "Proactive Breast",
    titleAccent: "Health",
    titlePart2: "at Your Fingertips",
    subtitle:
      "Ovula works with your Naibra thermal patch to monitor breast health — providing regular scans and peace of mind from the comfort of your home.",
    features: [
      {
        icon: "✿",
        title: "Naibra Smart Patch",
        desc: "A lightweight, non-invasive thermal sensor patch designed for regular at-home breast screening.",
      },
      {
        icon: "📶",
        title: "Wireless Bluetooth Link",
        desc: "Pair your Naibra patch wirelessly in seconds to sync and analyze readings automatically.",
      },
      {
        icon: "🏠",
        title: "At-Home Screening",
        desc: "Conduct medical-grade thermal tracking safely and comfortably without visiting a clinic.",
      },
    ],
    stat: "Non-invasive · Home-ready",
    accentWord: "Health",
    isFinal: false,
  },
  {
    phase: "STEP 02 · VISUALIZE & ANALYZE",
    phaseNum: "02",
    titlePart1: "Interactive 3D",
    titleAccent: "Thermal",
    titlePart2: "Dome Mapping",
    subtitle:
      "Visualize profiles across antenna channels — detect anomalies and monitor left-right deviation gradients over time.",
    features: [
      {
        icon: "📊",
        title: "Breast Dome Mapping",
        desc: "Sensor readings mapped onto an interactive 3D dome model with DMAS-CF location markers.",
      },
      {
        icon: "⚖️",
        title: "Left vs Right Asymmetry",
        desc: "Track differential deviations between sides to identify asymmetric changes early.",
      },
      {
        icon: "📈",
        title: "Historical Analytics",
        desc: "Compare current scans against baseline data to track trends and emerging variations.",
      },
    ],
    stat: "Multi-channel · 3D Visualized",
    accentWord: "Thermal",
    isFinal: false,
  },
  {
    phase: "STEP 03 · SAFE & PRIVATE",
    phaseNum: "03",
    titlePart1: "Encrypted, Safe",
    titleAccent: "& Actionable",
    titlePart2: "Health Reports",
    subtitle:
      "Your health records are completely private. Export clean summaries to share with your doctor or clinical partners with one tap.",
    features: [
      {
        icon: "🔐",
        title: "100% Private Data",
        desc: "Telemetry is stored locally on your device — your health information stays yours.",
      },
      {
        icon: "🔔",
        title: "Smart Screening Nudges",
        desc: "Receive monthly prompts to scan, helping you build a consistent health monitoring routine.",
      },
      {
        icon: "🩺",
        title: "Doctor-Ready PDF Reports",
        desc: "Generate clean, exportable summaries to share directly with your healthcare provider.",
      },
    ],
    stat: "Begin Your Health Journey",
    accentWord: "& Actionable",
    isFinal: true,
  },
] as const;

// -- Per-slide illustration components --

const PatchSensorIllustration: React.FC = () => {
  const { theme, isDark } = useAppTheme();
  const pulse1 = useRef(new Animated.Value(0.85)).current;
  const pulse2 = useRef(new Animated.Value(0.7)).current;
  const pulse3 = useRef(new Animated.Value(0.6)).current;
  const glow = useRef(new Animated.Value(0.5)).current;

  useEffect(() => {
    const loop = (anim: Animated.Value, delay: number, scale: number) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(delay),
          Animated.parallel([
            Animated.timing(anim, {
              toValue: scale,
              duration: 1400,
              useNativeDriver: true,
              easing: Easing.inOut(Easing.sin),
            }),
          ]),
          Animated.timing(anim, {
            toValue: 0.85,
            duration: 1400,
            useNativeDriver: true,
            easing: Easing.inOut(Easing.sin),
          }),
        ]),
      );
    loop(pulse1, 0, 1.1).start();
    loop(pulse2, 300, 1.18).start();
    loop(pulse3, 650, 1.28).start();
    Animated.loop(
      Animated.sequence([
        Animated.timing(glow, {
          toValue: 1,
          duration: 1600,
          useNativeDriver: true,
        }),
        Animated.timing(glow, {
          toValue: 0.4,
          duration: 1600,
          useNativeDriver: true,
        }),
      ]),
    ).start();
  }, []);

  const ring = (anim: Animated.Value, size: number, opacity: number) => (
    <Animated.View
      style={{
        position: "absolute",
        width: size,
        height: size,
        borderRadius: size / 2,
        borderWidth: 1.5,
        borderColor: theme.colors.primary,
        opacity: anim.interpolate({
          inputRange: [0.85, 1.28],
          outputRange: [opacity, 0],
        }),
        transform: [{ scale: anim }],
      }}
    />
  );

  return (
    <View style={illStyles.wrap}>
      {ring(pulse3, 130, 0.1)}
      {ring(pulse2, 105, 0.2)}
      {ring(pulse1, 82, 0.35)}
      <Animated.View style={[illStyles.patchOuter, { opacity: glow }]}>
        <LinearGradient
          colors={["#FF72B6", theme.colors.primary]}
          style={StyleSheet.absoluteFillObject}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
        />
        <Text style={illStyles.patchIcon}>✿</Text>
      </Animated.View>
      {/* Antenna dots */}
      {[0, 60, 120, 180, 240, 300].map((deg, i) => {
        const rad = (deg * Math.PI) / 180;
        const r = 44;
        return (
          <View
            key={i}
            style={[
              illStyles.antennaDot,
              {
                left: 75 + r * Math.cos(rad) - 4,
                top: 75 + r * Math.sin(rad) - 4,
                backgroundColor:
                  i % 3 === 0
                    ? theme.colors.primary
                    : i % 3 === 1
                      ? "#57CDB2"
                      : "#FFB65C",
              },
            ]}
          />
        );
      })}
    </View>
  );
};

const DomeIllustration: React.FC = () => {
  const { theme } = useAppTheme();
  const nodeGlow = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(nodeGlow, {
          toValue: 1,
          duration: 1200,
          useNativeDriver: true,
        }),
        Animated.timing(nodeGlow, {
          toValue: 0.3,
          duration: 1200,
          useNativeDriver: true,
        }),
      ]),
    ).start();
  }, []);

  const NODES = [
    { x: 75, y: 45, color: "#FF3D64", r: 6 },
    { x: 48, y: 62, color: "#FF3D64", r: 5 },
    { x: 102, y: 60, color: "#FFA531", r: 6 },
    { x: 35, y: 85, color: "#FFA531", r: 5 },
    { x: 115, y: 82, color: "#3FC98A", r: 5 },
    { x: 60, y: 95, color: "#3FC98A", r: 6 },
    { x: 90, y: 100, color: "#7FA9F0", r: 5 },
    { x: 75, y: 115, color: "#7FA9F0", r: 4 },
  ];
  const LINES = [
    [0, 1],
    [0, 2],
    [1, 3],
    [2, 4],
    [1, 5],
    [2, 6],
    [5, 7],
    [6, 7],
  ];

  return (
    <View style={illStyles.wrap}>
      {/* dome arc background */}
      <View
        style={[
          illStyles.domeArc,
          { borderColor: theme.colors.primary + "30" },
        ]}
      />
      <View
        style={[
          illStyles.domeArc,
          {
            width: 110,
            height: 110,
            top: 20,
            borderColor: theme.colors.primary + "18",
          },
        ]}
      />
      {LINES.map(([a, b], i) => {
        const na = NODES[a],
          nb = NODES[b];
        const dx = nb.x - na.x,
          dy = nb.y - na.y;
        const len = Math.sqrt(dx * dx + dy * dy);
        const angle = (Math.atan2(dy, dx) * 180) / Math.PI;
        return (
          <View
            key={i}
            style={{
              position: "absolute",
              left: na.x,
              top: na.y,
              width: len,
              height: 1,
              backgroundColor: theme.colors.primary + "25",
              transform: [{ rotate: `${angle}deg` }],
              transformOrigin: "left center",
            }}
          />
        );
      })}
      {NODES.map((n, i) => (
        <Animated.View
          key={i}
          style={[
            illStyles.domeNode,
            {
              left: n.x - n.r,
              top: n.y - n.r,
              width: n.r * 2,
              height: n.r * 2,
              borderRadius: n.r,
              backgroundColor: n.color,
              opacity: nodeGlow.interpolate({
                inputRange: [0, 1],
                outputRange: [0.5, 1],
              }),
              shadowColor: n.color,
              shadowOpacity: 0.6,
              shadowRadius: 6,
              elevation: 4,
            },
          ]}
        />
      ))}
    </View>
  );
};

const ReportIllustration: React.FC = () => {
  const { theme, isDark } = useAppTheme();
  const slideIn = useRef(new Animated.Value(20)).current;
  const fadeIn = useRef(new Animated.Value(0)).current;
  const shieldPulse = useRef(new Animated.Value(0.9)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(slideIn, {
        toValue: 0,
        duration: 600,
        useNativeDriver: true,
        easing: Easing.out(Easing.cubic),
      }),
      Animated.timing(fadeIn, {
        toValue: 1,
        duration: 600,
        useNativeDriver: true,
      }),
    ]).start();
    Animated.loop(
      Animated.sequence([
        Animated.timing(shieldPulse, {
          toValue: 1.1,
          duration: 1500,
          useNativeDriver: true,
        }),
        Animated.timing(shieldPulse, {
          toValue: 0.9,
          duration: 1500,
          useNativeDriver: true,
        }),
      ]),
    ).start();
  }, []);

  const checks = [
    "Thermal scan complete",
    "Asymmetry within range",
    "Report ready to export",
  ];
  return (
    <Animated.View
      style={[
        illStyles.reportCard,
        {
          backgroundColor: isDark ? "#1e2536" : "#FFFFFF",
          borderColor: isDark ? "rgba(240,85,158,0.15)" : "#FADAE8",
          opacity: fadeIn,
          transform: [{ translateY: slideIn }],
          shadowColor: theme.colors.primary,
          shadowOpacity: 0.1,
          shadowRadius: 16,
          elevation: 6,
        },
      ]}
    >
      <View style={illStyles.reportHeader}>
        <Text
          style={[
            illStyles.reportTitle,
            {
              color: theme.colors.primary,
              fontFamily: theme.typography.fontFamily.xbold,
            },
          ]}
        >
          ovula ✿
        </Text>
        <Animated.View
          style={[
            illStyles.shieldBadge,
            { transform: [{ scale: shieldPulse }] },
          ]}
        >
          <LinearGradient
            colors={["#FF72B6", theme.colors.primary]}
            style={StyleSheet.absoluteFillObject}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
          />
          <Text style={{ fontSize: 14 }}>🔐</Text>
        </Animated.View>
      </View>
      {checks.map((c, i) => (
        <View key={i} style={illStyles.checkRow}>
          <View
            style={[
              illStyles.checkCircle,
              { backgroundColor: theme.colors.success },
            ]}
          >
            <Text style={{ color: "#fff", fontSize: 10, fontWeight: "bold" }}>
              ✓
            </Text>
          </View>
          <Text
            style={[
              illStyles.checkText,
              {
                color: theme.colors.onSurface,
                fontFamily: theme.typography.fontFamily.bodyRegular,
              },
            ]}
          >
            {c}
          </Text>
        </View>
      ))}
      <View
        style={[
          illStyles.exportBtn,
          {
            backgroundColor: theme.colors.primary + "15",
            borderColor: theme.colors.primary + "30",
          },
        ]}
      >
        <Text
          style={[
            illStyles.exportBtnText,
            {
              color: theme.colors.primary,
              fontFamily: theme.typography.fontFamily.bodySemibold,
            },
          ]}
        >
          Export PDF Report →
        </Text>
      </View>
    </Animated.View>
  );
};

const ILLUSTRATIONS = [
  PatchSensorIllustration,
  DomeIllustration,
  ReportIllustration,
];

const FeatureRow: React.FC<{ icon: string; title: string; desc: string }> = ({
  icon,
  title,
  desc,
}) => {
  const { theme } = useAppTheme();

  const dynamicStyles = useMemo(
    () => ({
      row: {
        flexDirection: "row" as const,
        alignItems: "flex-start" as const,
        gap: 14,
        paddingVertical: 12,
      } as ViewStyle,
      iconWrap: {
        width: 44,
        height: 44,
        borderRadius: 14,
        backgroundColor: theme.colors.surfaceContainerHigh,
        alignItems: "center" as const,
        justifyContent: "center" as const,
        flexShrink: 0,
        borderWidth: 1,
        borderColor: theme.colors.primary + "20",
      } as ViewStyle,
      title: {
        fontSize: 16,
        fontFamily: theme.typography.fontFamily.bodySemibold,
        color: theme.colors.onSurface,
        letterSpacing: -0.1,
      } as TextStyle,
      desc: {
        fontSize: 13,
        fontFamily: theme.typography.fontFamily.bodyRegular,
        color: theme.colors.onSurfaceVariant,
        lineHeight: 18,
      } as TextStyle,
    }),
    [theme],
  );

  return (
    <View style={dynamicStyles.row}>
      <View style={dynamicStyles.iconWrap}>
        <Text style={{ fontSize: 20 }}>{icon}</Text>
      </View>
      <View style={{ flex: 1, gap: 2, paddingTop: 2 }}>
        <Text style={dynamicStyles.title}>{title}</Text>
        <Text style={dynamicStyles.desc}>{desc}</Text>
      </View>
    </View>
  );
};

export const OnboardingScreen: React.FC<Props> = ({ navigation }) => {
  const { theme, isDark } = useAppTheme();
  const insets = useSafeAreaInsets();
  const setHasCompletedOnboarding = useAuthStore(
    (s) => s.setHasCompletedOnboarding,
  );
  const [index, setIndex] = useState(0);
  const fadeAnim = useRef(new Animated.Value(1)).current;
  const slideY = useRef(new Animated.Value(0)).current;
  const transitioning = useRef(false);

  const slide = SLIDES[index];

  const navigateTo = useCallback(
    (next: number) => {
      if (transitioning.current) return;
      if (next < 0 || next >= SLIDES.length) return;
      transitioning.current = true;

      Animated.parallel([
        Animated.timing(fadeAnim, {
          toValue: 0,
          duration: 180,
          useNativeDriver: true,
          easing: Easing.out(Easing.ease),
        }),
        Animated.timing(slideY, {
          toValue: next > index ? -16 : 16,
          duration: 180,
          useNativeDriver: true,
        }),
      ]).start(() => {
        setIndex(next);
        slideY.setValue(next > index ? 16 : -16);
        Animated.parallel([
          Animated.timing(fadeAnim, {
            toValue: 1,
            duration: 300,
            useNativeDriver: true,
            easing: Easing.out(Easing.cubic),
          }),
          Animated.timing(slideY, {
            toValue: 0,
            duration: 300,
            useNativeDriver: true,
            easing: Easing.out(Easing.cubic),
          }),
        ]).start(() => {
          transitioning.current = false;
        });
      });
    },
    [index, fadeAnim, slideY],
  );

  const completeOnboarding = useCallback(() => {
    setHasCompletedOnboarding(true);
    navigation.replace("UserStack", { screen: "UserHome" });
  }, [navigation, setHasCompletedOnboarding]);

  const goNext = () => {
    if (index === SLIDES.length - 1) {
      completeOnboarding();
    } else {
      navigateTo(index + 1);
    }
  };

  const goPrev = () => navigateTo(index - 1);

  const skipToLogin = () => completeOnboarding();

  const dynamicStyles = useMemo(
    () => ({
      root: {
        flex: 1,
        backgroundColor: isDark ? "#0D111A" : "#FFF3F8",
      } as ViewStyle,
      glowBL: {
        position: "absolute" as const,
        bottom: 140,
        left: -60,
        width: 240,
        height: 240,
        borderRadius: 120,
        backgroundColor: theme.colors.primary,
        opacity: isDark ? 0.04 : 0.06,
      } as ViewStyle,
      glowTR: {
        position: "absolute" as const,
        top: 60,
        right: -60,
        width: 200,
        height: 200,
        borderRadius: 100,
        backgroundColor: theme.colors.primary,
        opacity: isDark ? 0.035 : 0.05,
      } as ViewStyle,
      logoName: {
        color: theme.colors.primary,
        fontSize: 22,
        fontFamily: theme.typography.fontFamily.xbold,
        letterSpacing: -0.3,
      } as TextStyle,
      skipPill: {
        paddingHorizontal: 16,
        paddingVertical: 8,
        borderRadius: theme.radius.pill,
        borderWidth: 1,
        borderColor: isDark ? "rgba(240,85,158,0.2)" : "#FADAE8",
        backgroundColor: isDark
          ? "rgba(240,85,158,0.06)"
          : "rgba(255,255,255,0.8)",
      } as ViewStyle,
      phaseBadge: {
        alignSelf: "flex-start" as const,
        paddingHorizontal: 12,
        paddingVertical: 5,
        borderRadius: theme.radius.pill,
        backgroundColor: theme.colors.primary + "15",
        borderWidth: 1,
        borderColor: theme.colors.primary + "25",
      } as ViewStyle,
      phaseText: {
        color: theme.colors.primary,
        fontSize: 10,
        fontFamily: theme.typography.fontFamily.headlineSemi,
        letterSpacing: 1.5,
        textTransform: "uppercase" as const,
      } as TextStyle,
      headlineLine: {
        fontSize: 28,
        fontFamily: theme.typography.fontFamily.displayBold,
        color: theme.colors.onSurface,
        letterSpacing: -0.4,
        lineHeight: 36,
      } as TextStyle,
      subtitle: {
        fontSize: 15,
        fontFamily: theme.typography.fontFamily.bodyRegular,
        color: theme.colors.onSurfaceVariant,
        lineHeight: 23,
        marginBottom: 20,
      } as TextStyle,
      featuresContainer: {
        backgroundColor: isDark ? "rgba(255,255,255,0.04)" : "#FFFFFF",
        borderRadius: 20,
        paddingHorizontal: 16,
        paddingVertical: 4,
        marginBottom: 20,
        borderWidth: 1,
        borderColor: isDark ? "rgba(240,85,158,0.1)" : "#FADAE8",
        shadowColor: theme.colors.primary,
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.06,
        shadowRadius: 12,
        elevation: 3,
      } as ViewStyle,
      footer: {
        paddingHorizontal: 24,
        paddingBottom: Math.max(insets.bottom, 20) + 10,
        paddingTop: 12,
        backgroundColor: isDark
          ? "rgba(30,37,54,0.95)"
          : "rgba(255,255,255,0.95)",
        borderTopWidth: 1,
        borderTopColor: isDark ? "rgba(240,85,158,0.08)" : "#FAEDF4",
        gap: 14,
      } as ViewStyle,
      navPrimaryWrap: {
        borderRadius: 16,
        overflow: "hidden" as const,
        shadowColor: theme.colors.primary,
        shadowOffset: { width: 0, height: 6 },
        shadowOpacity: 0.35,
        shadowRadius: 14,
        elevation: 8,
      } as ViewStyle,
      navPrimaryInner: {
        paddingHorizontal: 24,
        paddingVertical: 14,
        alignItems: "center" as const,
        justifyContent: "center" as const,
      } as ViewStyle,
      dot: {
        width: 6,
        height: 6,
        borderRadius: 3,
        backgroundColor: isDark ? "rgba(255,255,255,0.15)" : "#E8C9D8",
      } as ViewStyle,
      dotActive: {
        width: 24,
        borderRadius: 3,
        backgroundColor: theme.colors.primary,
      } as ViewStyle,
    }),
    [theme, isDark, insets],
  );

  const IllustrationComponent = ILLUSTRATIONS[index];

  return (
    <View style={dynamicStyles.root}>
      <StatusBar barStyle={isDark ? "light-content" : "dark-content"} />

      <View style={dynamicStyles.glowBL} />
      <View style={dynamicStyles.glowTR} />

      {/* Header */}
      <View style={[styles.header, { paddingTop: Math.max(insets.top, 48) }]}>
        <View style={styles.logoMark}>
          <Text style={dynamicStyles.logoName}>ovula ✿</Text>
        </View>
        <Pressable onPress={skipToLogin} style={dynamicStyles.skipPill}>
          <Text
            style={{
              color: theme.colors.onSurfaceVariant,
              fontSize: 13,
              fontFamily: theme.typography.fontFamily.bodyMedium,
            }}
          >
            Skip
          </Text>
        </Pressable>
      </View>

      <Animated.View
        style={[
          styles.slideWrap,
          {
            opacity: fadeAnim,
            transform: [{ translateY: slideY }],
          },
        ]}
      >
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          bounces={false}
        >
          {/* Phase badge */}
          <View style={styles.phaseRow}>
            <View style={dynamicStyles.phaseBadge}>
              <Text style={dynamicStyles.phaseText}>{slide.phase}</Text>
            </View>
          </View>

          {/* Headline */}
          <View style={styles.headlineBlock}>
            <Text style={dynamicStyles.headlineLine}>{slide.titlePart1}</Text>
            <Text
              style={[
                dynamicStyles.headlineLine,
                { color: theme.colors.primary },
              ]}
            >
              {slide.titleAccent}
            </Text>
            <Text style={dynamicStyles.headlineLine}>{slide.titlePart2}</Text>
          </View>

          {/* Mini illustration */}
          <View style={styles.illustrationWrap}>
            <IllustrationComponent />
          </View>

          {/* Subtitle */}
          <Text style={dynamicStyles.subtitle}>{slide.subtitle}</Text>

          {/* Features */}
          <View style={dynamicStyles.featuresContainer}>
            {slide.features.map((f, i) => (
              <View key={i}>
                <FeatureRow icon={f.icon} title={f.title} desc={f.desc} />
                {i < slide.features.length - 1 && (
                  <View
                    style={[
                      styles.tonalDivider,
                      { backgroundColor: theme.colors.primary, opacity: 0.08 },
                    ]}
                  />
                )}
              </View>
            ))}
          </View>

          {/* Final CTA */}
          {slide.isFinal && (
            <Pressable
              onPress={completeOnboarding}
              style={({ pressed }) => [
                styles.ctaBtnWrap,
                pressed && { opacity: 0.85 },
              ]}
            >
              <LinearGradient
                colors={["#FF72B6", theme.colors.primary]}
                style={styles.ctaBtn}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 0 }}
              >
                <Text style={styles.ctaBtnText}>Get Started 🚀</Text>
              </LinearGradient>
            </Pressable>
          )}

          <View style={{ height: 20 }} />
        </ScrollView>
      </Animated.View>

      {/* Footer Nav */}
      <View style={dynamicStyles.footer}>
        {/* Live bar */}
        <View
          style={[
            styles.liveBar,
            {
              backgroundColor: isDark
                ? "rgba(240,85,158,0.08)"
                : "rgba(255,105,180,0.08)",
              borderWidth: 1,
              borderColor: isDark ? "rgba(240,85,158,0.12)" : "#FADAE8",
            },
          ]}
        >
          <View
            style={[styles.liveDot, { backgroundColor: theme.colors.success }]}
          />
          <Text
            style={{
              color: theme.colors.onSurfaceDim,
              fontSize: 9,
              fontFamily: theme.typography.fontFamily.bodySemibold,
              letterSpacing: 0.5,
            }}
          >
            NAIBRA DEVICE
          </Text>
          <Text
            style={{
              color: theme.colors.onSurface,
              fontSize: 13,
              flex: 1,
              marginLeft: 8,
              fontFamily: theme.typography.fontFamily.bodyMedium,
            }}
          >
            {slide.stat}
          </Text>
        </View>

        {/* Navigation row */}
        <View style={styles.navRow}>
          <Pressable
            onPress={goPrev}
            style={[styles.navGhost, index === 0 && { opacity: 0.25 }]}
            disabled={index === 0}
          >
            <Text
              style={{
                color: theme.colors.onSurfaceVariant,
                fontSize: 12,
                fontFamily: theme.typography.fontFamily.bodySemibold,
                letterSpacing: 0.5,
              }}
            >
              ← BACK
            </Text>
          </Pressable>

          <View style={styles.dots}>
            {SLIDES.map((_, i) => (
              <View
                key={i}
                style={[
                  dynamicStyles.dot,
                  i === index && dynamicStyles.dotActive,
                ]}
              />
            ))}
          </View>

          <Pressable
            onPress={goNext}
            style={({ pressed }) => [
              dynamicStyles.navPrimaryWrap,
              pressed && { opacity: 0.85 },
            ]}
          >
            <LinearGradient
              colors={["#FF72B6", theme.colors.primary]}
              style={dynamicStyles.navPrimaryInner}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
            >
              <Text style={styles.navPrimaryText}>
                {index === SLIDES.length - 1 ? "START  →" : "NEXT  →"}
              </Text>
            </LinearGradient>
          </Pressable>
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 24,
    paddingBottom: 10,
  },
  logoMark: {
    flexDirection: "row",
    alignItems: "center",
  },
  slideWrap: { flex: 1 },
  scrollContent: {
    paddingHorizontal: 24,
    paddingBottom: 12,
  },
  phaseRow: { marginTop: 16, marginBottom: 12 },
  headlineBlock: {
    gap: 2,
    marginBottom: 16,
  },
  illustrationWrap: {
    alignItems: "center",
    marginBottom: 18,
    height: 160,
    justifyContent: "center",
  },
  tonalDivider: {
    height: 1,
    marginHorizontal: 4,
  },
  ctaBtnWrap: {
    borderRadius: 16,
    overflow: "hidden",
    marginBottom: 4,
    shadowColor: "#F0559E",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.35,
    shadowRadius: 14,
    elevation: 8,
  },
  ctaBtn: {
    height: 58,
    alignItems: "center",
    justifyContent: "center",
  },
  ctaBtnText: {
    color: "#FFFFFF",
    fontSize: 18,
    fontWeight: "bold",
    letterSpacing: 0.3,
  },
  liveBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  liveDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  navRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  navGhost: {
    paddingVertical: 10,
    paddingHorizontal: 4,
  },
  dots: {
    flexDirection: "row",
    gap: 7,
    alignItems: "center",
  },
  navPrimaryText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "bold",
    letterSpacing: 0.8,
  },
});

// Illustration shared styles
const illStyles = StyleSheet.create({
  wrap: {
    width: 150,
    height: 150,
    position: "relative",
    alignItems: "center",
    justifyContent: "center",
  },
  patchOuter: {
    width: 64,
    height: 64,
    borderRadius: 32,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#F0559E",
    shadowOpacity: 0.5,
    shadowRadius: 12,
    elevation: 8,
  },
  patchIcon: {
    fontSize: 32,
    color: "#FFFFFF",
    lineHeight: 36,
    textAlign: "center",
  },
  antennaDot: {
    position: "absolute",
    width: 8,
    height: 8,
    borderRadius: 4,
    shadowOpacity: 0.4,
    shadowRadius: 4,
    elevation: 3,
  },
  domeArc: {
    position: "absolute",
    width: 130,
    height: 130,
    borderRadius: 65,
    borderWidth: 1.5,
    top: 10,
  },
  domeNode: {
    position: "absolute",
    shadowOffset: { width: 0, height: 0 },
    elevation: 4,
  },
  reportCard: {
    width: 220,
    borderRadius: 18,
    borderWidth: 1,
    padding: 16,
    gap: 10,
  },
  reportHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  reportTitle: {
    fontSize: 16,
  },
  shieldBadge: {
    width: 34,
    height: 34,
    borderRadius: 10,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
  },
  checkRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  checkCircle: {
    width: 18,
    height: 18,
    borderRadius: 9,
    alignItems: "center",
    justifyContent: "center",
  },
  checkText: {
    fontSize: 12,
    flex: 1,
  },
  exportBtn: {
    borderRadius: 10,
    borderWidth: 1,
    paddingVertical: 8,
    paddingHorizontal: 12,
    alignItems: "center",
    marginTop: 2,
  },
  exportBtnText: {
    fontSize: 12,
  },
});
