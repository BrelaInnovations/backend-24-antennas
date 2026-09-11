import React from "react";
import { View, Text, StyleSheet, Pressable } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import { theme } from "../../../../theme";

interface Props {
  result: any;
  scannedSides?: ("left" | "right")[];
  onRescan: (side: "left" | "right") => void;
}

const VERDICT_COLORS: Record<string, string> = {
  healthy: theme.colors.success,
  monitor: theme.colors.warning,
};

export const ScanResultHero: React.FC<Props> = ({
  result,
  scannedSides = [],
  onRescan,
}) => {
  const availableSides =
    scannedSides.length > 0
      ? scannedSides
      : [
          ...(result?.left ? ["left"] : []),
          ...(result?.right ? ["right"] : []),
        ];

  const isSingle = availableSides.length === 1;

  const score = result?.left?.dot_count ?? result?.right?.dot_count ?? 0;
  const verdict = result?.metrics?.verdict_label ?? "Localization unavailable";
  const verdictColor = theme.colors.brandDark;

  return (
    <LinearGradient colors={theme.GradColors.soft} style={styles.hero}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Scan Complete</Text>

          <Text style={styles.subtitle}>DMAS-CF localization</Text>
        </View>

        <View
          style={[
            styles.status,
            {
              backgroundColor: verdictColor,
            },
          ]}
        >
          <Text style={styles.statusText}>{verdict}</Text>
        </View>
      </View>

      {/* Score */}
      <View style={styles.scoreBox}>
        <Text style={styles.score}>{score}</Text>

        <Text style={styles.scoreLabel}>Displayed locations · shared capture</Text>
      </View>

      {/* Scan sides */}
      <Text style={styles.sectionTitle}>Scanned sides</Text>

      <View style={styles.sideRow}>
        {(["left", "right"] as const).map((side) => {
          const scanned = availableSides.includes(side);

          const sideScore = result?.[side]?.dot_count ?? 0;

          return (
            <View
              key={side}
              style={[styles.sideCard, scanned && styles.sideCardActive]}
            >
              <Ionicons
                name={side === "left" ? "body-outline" : "body"}
                size={20}
                color={scanned ? theme.colors.brandDark : theme.colors.inkSoft}
              />

              <Text style={styles.sideName}>
                {side === "left" ? "Left" : "Right"}
              </Text>

              <Text style={styles.sideScore}>{scanned ? sideScore : "--"}</Text>
            </View>
          );
        })}
      </View>

      {/* Rescan actions */}
      <Text style={styles.sectionTitle}>Scan another side</Text>

      <View style={styles.actionRow}>
        {(["left", "right"] as const).map((side) => {
          const scanned = availableSides.includes(side);

          return (
            <Pressable
              key={side}
              onPress={() => onRescan(side)}
              style={[styles.action, !scanned && styles.actionActive]}
            >
              <Ionicons
                name={scanned ? "refresh" : "scan-outline"}
                size={18}
                color={scanned ? theme.colors.inkSoft : theme.colors.brandDark}
              />

              <Text
                style={[styles.actionText, !scanned && styles.actionTextActive]}
              >
                {scanned ? `Rescan ${side}` : `Scan ${side}`}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </LinearGradient>
  );
};

const styles = StyleSheet.create({
  hero: {
    marginHorizontal: theme.spacing2.lg,
    borderRadius: theme.radius.lg,
    paddingHorizontal: theme.spacing2.lg,
    paddingVertical: theme.spacing2.lg,
    ...theme.shadow.card,
  },

  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },

  title: {
    fontFamily: theme.typography.fontFamily.xbold,
    fontSize: 16,
    color: theme.colors.ink,
  },

  subtitle: {
    marginTop: 2,
    fontFamily: theme.typography.fontFamily.bold,
    fontSize: 11,
    color: theme.colors.inkSoft,
  },

  status: {
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 18,
  },

  statusText: {
    fontFamily: theme.typography.fontFamily.xbold,
    fontSize: 11,
    color: "#1F3A34",
  },

  scoreBox: {
    alignItems: "center",
    marginVertical: 2,
  },

  score: {
    fontFamily: theme.typography.fontFamily.xbold,
    fontSize: 56,
    lineHeight: 58,
    color: theme.colors.ink,
  },

  scoreLabel: {
    marginTop: -2,
    fontFamily: theme.typography.fontFamily.bold,
    fontSize: 12,
    color: theme.colors.inkSoft,
  },

  sectionTitle: {
    marginTop: 8,
    marginBottom: 6,
    fontFamily: theme.typography.fontFamily.bold,
    fontSize: 11,
    color: theme.colors.inkSoft,
  },

  sideRow: {
    flexDirection: "row",
    gap: 12,
  },

  sideCard: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: "rgba(255,255,255,0.55)",
  },

  sideCardActive: {
    backgroundColor: "#FFF",
  },

  sideName: {
    marginTop: 4,
    fontFamily: theme.typography.fontFamily.bold,
    fontSize: 12,
    color: theme.colors.inkSoft,
  },

  sideScore: {
    marginTop: 2,
    fontFamily: theme.typography.fontFamily.xbold,
    fontSize: 18,
    color: theme.colors.ink,
  },

  actionRow: {
    flexDirection: "row",
    gap: 12,
    marginTop: 2,
  },

  action: {
    flex: 1,
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    gap: 5,
    paddingVertical: 14,
    borderRadius: 10,
    backgroundColor: "rgba(246, 246, 246, 0.6)",
  },

  actionActive: {
    backgroundColor: "#fed4e8ff",
  },

  actionText: {
    fontFamily: theme.typography.fontFamily.bold,
    fontSize: 12,
    color: theme.colors.inkSoft,
  },

  actionTextActive: {
    color: theme.colors.brandDark,
  },
});
