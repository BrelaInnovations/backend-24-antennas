import React, { forwardRef } from "react";
import {
  View,
  Text,
  Pressable,
  StyleSheet,
  useWindowDimensions,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import ViewShot from "react-native-view-shot";
import { theme } from "../../../../theme";
import Dome3D from "../../../../components/common/Dome3D";

interface Props {
  result: any;
  onOpenDome: (side: "left" | "right") => void;
  leftRef: React.RefObject<ViewShot>;
  rightRef: React.RefObject<ViewShot>;
  scannedSides?: ("left" | "right")[];
}

export const ScanResultDomes: React.FC<Props> = ({
  result,
  onOpenDome,
  leftRef,
  rightRef,
  scannedSides = [],
}) => {
  const { width } = useWindowDimensions();
  const domeCardSize =
    (width - theme.spacing2.lg * 2 - theme.spacing2.md) / 2 - theme.spacing2.sm;

  // Only show sides that have been scanned
  const availableSides: Array<"left" | "right"> =
    scannedSides.length > 0
      ? scannedSides
      : (() => {
          const sides: Array<"left" | "right"> = [];
          if (result.left) sides.push("left");
          if (result.right) sides.push("right");
          return sides;
        })();

  // Determine if we have single or double dome
  const isSingleDome = availableSides.length === 1;
  const isDoubleDome = availableSides.length === 2;

  if (availableSides.length === 0) {
    return null; // No sides scanned yet
  }

  return (
    <>
      <Text style={styles.domesTitle}>
        {isSingleDome
          ? `${availableSides[0] === "left" ? "Left" : "Right"} breast profile · drag to rotate`
          : "Your breast profiles · drag to rotate"}
      </Text>
      <View
        style={[styles.resultDomes, isSingleDome && styles.resultDomesSingle]}
      >
        {availableSides.map((side) => (
          <View
            key={side}
            style={[
              styles.resultDomeCard,
              isSingleDome && styles.resultDomeCardSingle,
            ]}
            testID={`scan-result-dome-${side}`}
          >
            <ViewShot
              ref={side === "left" ? leftRef : rightRef}
              options={{ format: "png", result: "base64", quality: 1 }}
            >
              <Dome3D
                size={
                  isSingleDome
                    ? domeCardSize * 2 + theme.spacing2.md
                    : domeCardSize
                }
                dots={result[side]?.dots || []}
                antennas={result.antennas || []}
                showAntennas={false}
              />
            </ViewShot>
            <Pressable
              testID={`scan-result-dome-${side}-open`}
              style={styles.resultDomeBtn}
              onPress={() => onOpenDome(side)}
            >
              <Text style={styles.resultDomeLabel}>
                {side === "left" ? "Left" : "Right"} ·{" "}
                {result[side]?.dot_count ?? 0} locations
              </Text>
              <Ionicons
                name="expand-outline"
                size={14}
                color={theme.colors.brandDark}
              />
            </Pressable>
          </View>
        ))}
      </View>
    </>
  );
};

const styles = StyleSheet.create({
  domesTitle: {
    fontFamily: theme.typography.fontFamily.xbold,
    fontSize: 15,
    color: theme.colors.ink,
    marginHorizontal: theme.spacing2.lg,
    marginTop: theme.spacing2.lg,
    marginBottom: theme.spacing2.sm,
  },
  resultDomes: {
    flexDirection: "row",
    gap: theme.spacing2.md,
    paddingHorizontal: theme.spacing2.lg,
  },
  resultDomesSingle: {
    justifyContent: "center",
  },
  resultDomeCard: {
    flex: 1,
    alignItems: "center",
    backgroundColor: theme.colors.surface2,
    borderRadius: theme.radius.lg,
    paddingVertical: theme.spacing2.sm,
    borderWidth: 1,
    borderColor: theme.colors.border,
    ...theme.shadow.card,
  },
  resultDomeCardSingle: {
    maxWidth: 400,
    alignSelf: "center",
  },
  resultDomeBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingVertical: 6,
    paddingHorizontal: theme.spacing2.md,
    backgroundColor: theme.colors.surface3,
    borderRadius: theme.radius.pill,
  },
  resultDomeLabel: {
    fontFamily: theme.typography.fontFamily.bold,
    fontSize: 12,
    color: theme.colors.brandDark,
  },
});
