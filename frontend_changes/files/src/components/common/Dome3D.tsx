import React, { useMemo, useRef, useState } from "react";
import { PanResponder, View } from "react-native";
import Svg, {
  Circle,
  Defs,
  Line,
  Path,
  Polyline,
  RadialGradient,
  Stop,
} from "react-native-svg";
import { useAppTheme } from "../../theme/ThemeProvider";

export type DomeDot = { x: number; y: number; z: number; s?: number; c?: string; intensity?: number; source?: string };
export type DomeAntenna = {
  id: string;
  x: number;
  y: number;
  z: number;
  prong: number;
  label?: string;
};

type Props = {
  size: number;
  dots?: DomeDot[];
  antennas?: DomeAntenna[];
  visible?: Record<string, boolean>;
  interactive?: boolean;
  showAntennas?: boolean;
  activeIds?: string[];
  showBeams?: boolean;
  pulsePhase?: number; // 0..1, drives irradiation ripple radius during scan
  testID?: string;
};

const ALL_VISIBLE = { high: true, medium: true, low: true, baseline: true };

function rotatePoint(
  p: { x: number; y: number; z: number },
  yaw: number,
  pitch: number,
) {
  const cy = Math.cos(yaw),
    sy = Math.sin(yaw);
  const x1 = p.x * cy - p.y * sy;
  const y1 = p.x * sy + p.y * cy;
  const cp = Math.cos(pitch),
    sp = Math.sin(pitch);
  const y2 = y1 * cp - p.z * sp;
  const z2 = y1 * sp + p.z * cp;
  return { x: x1, y: y2, z: z2 }; // y = depth, z = up
}

// Monotone-chain convex hull — the hemisphere is convex, so the hull of its
// projected boundary curves (base ring + visible silhouette arc) is its outline.
function convexHull(pts: { x: number; y: number }[]) {
  const p = [...pts].sort((a, b) => a.x - b.x || a.y - b.y);
  if (p.length < 3) return p;
  const cross = (o: any, a: any, b: any) =>
    (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
  const lower: any[] = [];
  for (const pt of p) {
    while (
      lower.length >= 2 &&
      cross(lower[lower.length - 2], lower[lower.length - 1], pt) <= 0
    )
      lower.pop();
    lower.push(pt);
  }
  const upper: any[] = [];
  for (let i = p.length - 1; i >= 0; i--) {
    const pt = p[i];
    while (
      upper.length >= 2 &&
      cross(upper[upper.length - 2], upper[upper.length - 1], pt) <= 0
    )
      upper.pop();
    upper.push(pt);
  }
  lower.pop();
  upper.pop();
  return lower.concat(upper);
}

export default function Dome3D({
  size,
  dots = [],
  antennas = [],
  visible = ALL_VISIBLE,
  interactive = true,
  showAntennas = true,
  activeIds = [],
  showBeams = false,
  pulsePhase = 0,
  testID,
}: Props) {
  const { theme } = useAppTheme();
  const [rot, setRot] = useState({ yaw: Math.PI, pitch: -Math.PI / 2 });
  const start = useRef({ yaw: Math.PI, pitch: -Math.PI / 2 });

  const SEV_COLORS: Record<string, string> = {
    high: theme.colors.sevHigh,
    medium: theme.colors.sevMedium,
    low: theme.colors.sevLow,
    baseline: theme.colors.sevBaseline,
  };

  const pan = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => interactive,
      onMoveShouldSetPanResponder: (_e, g) =>
        interactive && (Math.abs(g.dx) > 4 || Math.abs(g.dy) > 4),
      onPanResponderGrant: () => {
        start.current = { ...rotRef.current };
      },
      onPanResponderMove: (_e, g) => {
        const yaw = start.current.yaw + g.dx * 0.012;
        const pitch = Math.max(
          -Math.PI / 2,
          Math.min(0.35, start.current.pitch + g.dy * 0.008),
        );
        rotRef.current = { yaw, pitch };
        setRot({ yaw, pitch });
      },
    }),
  ).current;
  const rotRef = useRef(rot);

  const scale = size * 0.37;
  const cx = size / 2;
  const cyc = size * 0.56;
  const proj = (p: { x: number; y: number; z: number }) => {
    const r = rotatePoint(p, rot.yaw, rot.pitch);
    return { sx: cx + r.x * scale, sy: cyc - r.z * scale, depth: r.y };
  };

  // Hemisphere outline: base ring + silhouette arc (points where the surface
  // normal is perpendicular to the view direction, kept only for z >= 0).
  const outline = useMemo(() => {
    const raw: { x: number; y: number }[] = [];
    const basePts: string[] = [];
    for (let i = 0; i <= 48; i++) {
      const th = (i / 48) * Math.PI * 2;
      const p = proj({ x: Math.cos(th), y: Math.sin(th), z: 0 });
      raw.push({ x: p.sx, y: p.sy });
      basePts.push(`${p.sx.toFixed(1)},${p.sy.toFixed(1)}`);
    }
    // view direction in model space (depth axis)
    const cp = Math.cos(rot.pitch),
      sp = Math.sin(rot.pitch);
    const v = [Math.sin(rot.yaw) * cp, Math.cos(rot.yaw) * cp, -sp];
    const n = Math.hypot(v[0], v[1]);
    if (n > 1e-4) {
      const u = [v[1] / n, -v[0] / n, 0];
      const w = [
        v[1] * u[2] - v[2] * u[1],
        v[2] * u[0] - v[0] * u[2],
        v[0] * u[1] - v[1] * u[0],
      ];
      for (let i = 0; i < 48; i++) {
        const phi = (i / 48) * Math.PI * 2;
        const c = Math.cos(phi),
          s = Math.sin(phi);
        const pz = u[2] * c + w[2] * s;
        if (pz < -0.01) continue;
        const p = proj({
          x: u[0] * c + w[0] * s,
          y: u[1] * c + w[1] * s,
          z: pz,
        });
        raw.push({ x: p.sx, y: p.sy });
      }
    }
    const hull = convexHull(raw);
    const path =
      hull
        .map(
          (p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`,
        )
        .join(" ") + " Z";
    return { path, base: basePts.join(" ") };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rot, size]);

  // Wireframe: latitude rings + prong meridians
  const wire = useMemo(() => {
    const rings: string[] = [];
    for (const polar of [0.28, 0.55, 0.85, 1.15, Math.PI / 2]) {
      const pts: string[] = [];
      for (let i = 0; i <= 40; i++) {
        const th = (i / 40) * Math.PI * 2;
        const p = proj({
          x: Math.sin(polar) * Math.cos(th),
          y: Math.sin(polar) * Math.sin(th),
          z: Math.cos(polar),
        });
        pts.push(`${p.sx.toFixed(1)},${p.sy.toFixed(1)}`);
      }
      rings.push(pts.join(" "));
    }
    const prongSet = new Set(antennas.map((a) => a.prong));
    const nProngs = prongSet.size || 12;
    const meridians: string[] = [];
    for (let pr = 0; pr < nProngs; pr++) {
      const th = (2 * Math.PI * pr) / nProngs;
      const pts: string[] = [];
      for (let i = 0; i <= 14; i++) {
        const polar = (i / 14) * (Math.PI / 2);
        const p = proj({
          x: Math.sin(polar) * Math.cos(th),
          y: Math.sin(polar) * Math.sin(th),
          z: Math.cos(polar),
        });
        pts.push(`${p.sx.toFixed(1)},${p.sy.toFixed(1)}`);
      }
      meridians.push(pts.join(" "));
    }
    return { rings, meridians };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rot, size, antennas.length]);

  const projDots = useMemo(() => {
    return dots
      .filter((d) => d.source === "dmas-cf" && [d.x, d.y, d.z].every(Number.isFinite))
      .map((d) => proj(d))
      .sort((a, b) => b.depth - a.depth); // far first
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dots, rot, visible, size]);

  const projAnts = useMemo(() => {
    return antennas.map((a) => ({ ...a, ...proj(a) }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [antennas, rot, size]);

  const apex = proj({ x: 0, y: 0, z: 1 });
  const activeSet = new Set(activeIds);
  const activeAnts = projAnts.filter((a) => activeSet.has(a.id));

  // beams: from active antenna to sampled others (visual "irradiation" lines)
  const beams: { x1: number; y1: number; x2: number; y2: number }[] = [];
  if (showBeams && activeAnts.length > 0 && projAnts.length > 4) {
    const src = activeAnts[0];
    for (let j = 0; j < projAnts.length; j += 7) {
      const t = projAnts[j];
      if (t.id === src.id) continue;
      beams.push({ x1: src.sx, y1: src.sy, x2: t.sx, y2: t.sy });
    }
  }

  return (
    <View
      style={{ width: size, height: size }}
      testID={testID}
      {...(interactive ? pan.panHandlers : {})}
    >
      <Svg width={size} height={size}>
        <Defs>
          <RadialGradient id="skin" cx="42%" cy="38%" r="65%">
            <Stop offset="0%" stopColor="#FFE3EE" stopOpacity="0.9" />
            <Stop offset="55%" stopColor="#FBC8DD" stopOpacity="0.5" />
            <Stop offset="100%" stopColor="#F6A4C9" stopOpacity="0.16" />
          </RadialGradient>
          <RadialGradient id="nipple" cx="50%" cy="50%" r="50%">
            <Stop offset="0%" stopColor="#E88BB4" stopOpacity="0.95" />
            <Stop offset="100%" stopColor="#E88BB4" stopOpacity="0" />
          </RadialGradient>
        </Defs>

        {/* translucent breast dome (hemisphere) */}
        <Path
          d={outline.path}
          fill="url(#skin)"
          stroke="#F2A9C9"
          strokeOpacity={0.6}
          strokeWidth={1.6}
          strokeLinejoin="round"
        />
        {/* patch base ring */}
        <Polyline
          points={outline.base}
          fill="none"
          stroke="#E19BC0"
          strokeOpacity={0.55}
          strokeWidth={1.4}
        />

        {/* wireframe */}
        {wire.rings.map((pts, i) => (
          <Polyline
            key={`r${i}`}
            points={pts}
            fill="none"
            stroke="#E19BC0"
            strokeOpacity={0.32}
            strokeWidth={1}
          />
        ))}
        {wire.meridians.map((pts, i) => (
          <Polyline
            key={`m${i}`}
            points={pts}
            fill="none"
            stroke="#C9B4EE"
            strokeOpacity={0.3}
            strokeWidth={1}
          />
        ))}

        {/* irradiation beams */}
        {beams.map((b, i) => (
          <Line
            key={`b${i}`}
            {...b}
            stroke={theme.colors.brandDark}
            strokeOpacity={0.35}
            strokeWidth={1.2}
            strokeDasharray="3,3"
          />
        ))}

        {/* DMAS-CF location markers */}
        {projDots.map((d, i) => {
          const depthNorm = Math.max(0, Math.min(1, (1 - d.depth) / 2));
          const r = 2.4 + depthNorm * 0.8;
          return (
            <Circle
              key={`d${i}`}
              cx={d.sx}
              cy={d.sy}
              r={r * (size / 320)}
              fill="#7C3AED"
              opacity={0.32 + depthNorm * 0.55}
            />
          );
        })}

        {/* nipple / apex reference */}
        <Circle
          cx={apex.sx}
          cy={apex.sy}
          r={scale * 0.09}
          fill="url(#nipple)"
        />

        {/* antenna markers on patch */}
        {showAntennas &&
          projAnts.map((a) => {
            const active = activeSet.has(a.id);
            const front = a.depth < 0.15;
            return (
              <React.Fragment key={a.id}>
                {active && (
                  <Circle
                    cx={a.sx}
                    cy={a.sy}
                    r={4 + pulsePhase * 14 * (size / 320)}
                    fill="none"
                    stroke={theme.colors.brandDark}
                    strokeOpacity={Math.max(0, 0.8 - pulsePhase * 0.8)}
                    strokeWidth={2}
                  />
                )}
                <Circle
                  cx={a.sx}
                  cy={a.sy}
                  r={(active ? 4.4 : 2.6) * (size / 320)}
                  fill={
                    active ? theme.colors.brandDark : theme.colors.lavenderDark
                  }
                  opacity={active ? 1 : front ? 0.9 : 0.35}
                  stroke="#FFFFFF"
                  strokeWidth={active ? 1.2 : 0.6}
                />
              </React.Fragment>
            );
          })}
      </Svg>
    </View>
  );
}
