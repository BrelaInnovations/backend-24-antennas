import React, {
  Suspense,
  useMemo,
  useRef,
  useCallback,
  useEffect,
} from "react";
import { Canvas, useFrame } from "@react-three/fiber/native";
import { OrbitControls } from "@react-three/drei/native";
import * as THREE from "three";
import type { DomeDot, DomeAntenna } from "../Dome3D";
import { useAppTheme } from "../../../theme/ThemeProvider";
import SnapshotTrigger from "./SnapShot";
import { ActivityIndicator } from "react-native";

const ALL_VISIBLE = { high: true, medium: true, low: true, baseline: true };
const LATITUDE_POLARS = [0.28, 0.55, 0.85, 1.15, Math.PI / 2];
const DOME_RADIUS = 2.1;
const SEGMENTS = 48;
const GLYPH_W = 5;
const GLYPH_H = 7;
const GLYPH_GAP = 1;
const QUADRANT_LABEL_TEXT: Record<Quadrant, string> = {
  uiq: "UIQ",
  liq: "LIQ",
  uoq: "UOQ",
  loq: "LOQ",
};

const LABEL_RADIUS = DOME_RADIUS + 0.22;
const LABEL_PLANE_HEIGHT = 0.16;

const GLYPHS: Record<string, number[]> = {
  U: [0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0e],
  I: [0x1f, 0x04, 0x04, 0x04, 0x04, 0x04, 0x1f],
  Q: [0x0e, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0d],
  O: [0x0e, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0e],
  L: [0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1f],
};

const QUADRANTS = [
  {
    id: "uiq" as Quadrant,
    phiStart: -Math.PI / 4,
    phiEnd: Math.PI / 4,
    phiMid: 0,
  },
  {
    id: "uoq" as Quadrant,
    phiStart: Math.PI / 4,
    phiEnd: (3 * Math.PI) / 4,
    phiMid: Math.PI / 2,
  },
  {
    id: "loq" as Quadrant,
    phiStart: (3 * Math.PI) / 4,
    phiEnd: (5 * Math.PI) / 4,
    phiMid: Math.PI,
  },
  {
    id: "liq" as Quadrant,
    phiStart: (5 * Math.PI) / 4,
    phiEnd: (7 * Math.PI) / 4,
    phiMid: -Math.PI / 2,
  },
];

const labelTextureCache = new Map<string, THREE.DataTexture>();

export type Quadrant = "uiq" | "liq" | "uoq" | "loq";

export type SnapshotAction = {
  capture: () => Promise<string | null>;
  snapshot: string | null;
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
  pulsePhase?: number;
  testID?: string;
  onQuadrantSelect?: (quadrant: Quadrant | null) => void;
  selectedQuadrant?: Quadrant | null;
  loading?: boolean;
  error?: string | null;
  cameraPosition?: [number, number, number];
  snapshotActionRef?: React.MutableRefObject<SnapshotAction | null>;
};

function usePalette(theme: any) {
  return useMemo(
    () => ({
      brandDark: theme.colors.brandDark ?? "#FDE6EF",
      lineSecondary: theme.colors.lineSecondary ?? "#E19BC0",
      lavender: theme.colors.lavender ?? "#D8C6F5",
      lavenderDark: theme.colors.lavenderDark ?? "#a855f7",
      brand: theme.colors.brand ?? "#F2A9C9",
      primary: theme.colors.primary ?? "#2fd9a8",
      sevHigh: theme.colors.sevHigh ?? "#ff4757",
      sevMedium: theme.colors.sevMedium ?? "#ffa502",
      sevLow: theme.colors.sevLow ?? "#2ed573",
      sevBaseline: theme.colors.sevBaseline ?? "#1e90ff",
      apexColor: theme.colors.apexColor,
      apexEmissive: theme.colors.apexEmissive,
      inkFaint: theme.colors.inkFaint ?? "#9a7a8a",
      brandDarkFallbackTeal: theme.colors.brandDark ?? "#2fd9a8",
      brandDarkFallbackPink: theme.colors.brandDark ?? "#ff9bb2",
      lavenderFallback: theme.colors.lavender ?? "#E7D6FF",
    }),
    [
      theme.colors.brandDark,
      theme.colors.lineSecondary,
      theme.colors.lavender,
      theme.colors.lavenderDark,
      theme.colors.brand,
      theme.colors.primary,
      theme.colors.sevHigh,
      theme.colors.sevMedium,
      theme.colors.sevLow,
      theme.colors.sevBaseline,
      theme.colors.apexColor,
      theme.colors.apexEmissive,
      theme.colors.inkFaint,
    ],
  );
}

function getQuadrantFromArray(x: number, y: number): Quadrant {
  const phi = Math.atan2(y, x);

  const normalizedPhi = phi < -Math.PI / 4 ? phi + Math.PI * 2 : phi;

  const match = QUADRANTS.find((q) => {
    let start = q.phiStart;
    let end = q.phiEnd;

    if (start < -Math.PI / 4) start += Math.PI * 2;
    if (end < start) end += Math.PI * 2;

    return normalizedPhi >= start && normalizedPhi < end;
  });

  return match?.id ?? "uiq";
}

function buildLabelTexture(text: string): THREE.DataTexture {
  const cached = labelTextureCache.get(text);
  if (cached) return cached;

  const chars = text.toUpperCase().split("");
  const width = chars.length * (GLYPH_W + GLYPH_GAP) - GLYPH_GAP;
  const height = GLYPH_H;
  const data = new Uint8Array(width * height * 4); // RGBA, transparent by default

  chars.forEach((ch, ci) => {
    const rows = GLYPHS[ch];
    if (!rows) return;
    const xOffset = ci * (GLYPH_W + GLYPH_GAP);
    for (let row = 0; row < GLYPH_H; row++) {
      const bits = rows[row];
      for (let col = 0; col < GLYPH_W; col++) {
        const on = (bits >> (GLYPH_W - 1 - col)) & 1;
        if (!on) continue;
        const px = xOffset + col;
        const py = row;
        const idx = (py * width + px) * 4;
        data[idx + 0] = 255; // R — actual color applied via material.color, texture is white+alpha
        data[idx + 1] = 255;
        data[idx + 2] = 255;
        data[idx + 3] = 255; // A — opaque glyph pixel, transparent elsewhere
      }
    }
  });

  const texture = new THREE.DataTexture(data, width, height, THREE.RGBAFormat);
  texture.flipY = true;
  texture.magFilter = THREE.NearestFilter;
  texture.minFilter = THREE.NearestFilter;
  texture.needsUpdate = true;

  labelTextureCache.set(text, texture);
  return texture;
}

function CenteredMessage({
  size,
  children,
}: {
  size: number;
  children: React.ReactNode;
}) {
  const { View } = require("react-native");
  return (
    <View
      style={{
        width: size,
        height: size,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {children}
    </View>
  );
}

function toThree(p: {
  x: number;
  y: number;
  z: number;
}): [number, number, number] {
  return [p.x * DOME_RADIUS, p.z * DOME_RADIUS, -p.y * DOME_RADIUS];
}

const HemisphereMesh = React.memo(function HemisphereMesh({
  palette,
  selectedQuadrant,
}: {
  palette: any;
  selectedQuadrant?: Quadrant | null;
}) {

  const geometry = useMemo(() => {
    const geo = new THREE.SphereGeometry(DOME_RADIUS, 48, 24, 0, Math.PI * 2, 0, Math.PI / 2);
    geo.computeVertexNormals();
    return geo;
  }, []);

  const opacity = selectedQuadrant ? 0.08 : 0.2;

  return (
    <mesh
      geometry={geometry}
      receiveShadow={false}
      castShadow={false}
    >
      <meshBasicMaterial
        color={palette.brandDark}
        transparent
        opacity={opacity}
        // roughness={0.2}
        // metalness={0}
        // clearcoat={0.05}
        // clearcoatRoughness={0.04}
        side={THREE.FrontSide}
        depthWrite={false}
      />
    </mesh>
  );
});

const LatitudeRings = React.memo(function LatitudeRings({
  palette,
  selectedQuadrant,
}: {
  palette: any;
  selectedQuadrant?: Quadrant | null;
}) {
  const geometries = useMemo(() => {
    return LATITUDE_POLARS.map((polar) => {
      const ringR = Math.sin(polar) * DOME_RADIUS;
      const ringY = Math.cos(polar) * DOME_RADIUS;
      const points: THREE.Vector3[] = [];
      const segs = 64;
      for (let i = 0; i <= segs; i++) {
        const t = (i / segs) * Math.PI * 2;
        points.push(
          new THREE.Vector3(Math.cos(t) * ringR, ringY, Math.sin(t) * ringR),
        );
      }
      const curve = new THREE.CatmullRomCurve3(points, true);
      return new THREE.TubeGeometry(curve, 64, 0.005, 6, true);
    });
  }, []);

  return (
    <group>
      {geometries.map((geo, i) => (
        <mesh key={i} geometry={geo}>
          <meshBasicMaterial
            color={palette.lineSecondary}
            transparent
            opacity={selectedQuadrant ? 0.18 : 0.32}
          />
        </mesh>
      ))}
    </group>
  );
});

const Meridians = React.memo(function Meridians({
  antennas,
  palette,
}: {
  antennas: DomeAntenna[];
  palette: any;
}) {
  const nProngs = useMemo(() => {
    const set = new Set(antennas.map((a) => a.prong));
    return set.size || 12;
  }, [antennas]);

  const arcGeo = useMemo(() => {
    const points: THREE.Vector3[] = [];
    const segs = 24;
    for (let i = 0; i <= segs; i++) {
      const polar = (i / segs) * (Math.PI / 2);
      points.push(
        new THREE.Vector3(
          Math.sin(polar) * DOME_RADIUS,
          Math.cos(polar) * DOME_RADIUS,
          0,
        ),
      );
    }
    const curve = new THREE.CatmullRomCurve3(points);
    return new THREE.TubeGeometry(curve, segs, 0.004, 6, false);
  }, []);

  const quadrantArcGeo = useMemo(() => {
    const points: THREE.Vector3[] = [];
    const segs = 24;
    for (let i = 0; i <= segs; i++) {
      const polar = (i / segs) * (Math.PI / 2);
      points.push(
        new THREE.Vector3(
          Math.sin(polar) * DOME_RADIUS,
          Math.cos(polar) * DOME_RADIUS,
          0,
        ),
      );
    }
    const curve = new THREE.CatmullRomCurve3(points);
    return new THREE.TubeGeometry(curve, segs, 0.008, 6, false);
  }, []);

  return (
    <group>
      {Array.from({ length: nProngs }).map((_, i) => {
        const th = (2 * Math.PI * i) / nProngs;
        return (
          <mesh key={`m-${i}`} geometry={arcGeo} rotation={[0, th, 0]}>
            <meshBasicMaterial
              color={palette.lavender}
              transparent
              opacity={0.26}
            />
          </mesh>
        );
      })}
      {[0, Math.PI / 2, Math.PI, (3 * Math.PI) / 2].map((th, i) => (
        <mesh key={`q-${i}`} geometry={quadrantArcGeo} rotation={[0, th, 0]}>
          <meshBasicMaterial color={palette.brand} transparent opacity={0.5} />
        </mesh>
      ))}
    </group>
  );
});

const BaseRing = React.memo(function BaseRing({ palette }: { palette: any }) {
  return (
    <mesh rotation={[Math.PI / 2, 0, 0]}>
      <torusGeometry args={[DOME_RADIUS, 0.01, 16, 64]} />
      <meshBasicMaterial
        color={palette.lineSecondary}
        transparent
        opacity={0.25}
      />
    </mesh>
  );
});

const QuadrantZones = React.memo(function QuadrantZones({
  onQuadrantSelect,
  selectedQuadrant,
  palette,
}: {
  onQuadrantSelect?: (q: Quadrant | null) => void;
  selectedQuadrant: Quadrant | null;
  palette: any;
}) {
  const geometries = useMemo(
    () =>
      QUADRANTS.map((q) => ({
        id: q.id,
        geo: new THREE.SphereGeometry(
          DOME_RADIUS + 0.01,
          40,
          40,
          q.phiStart,
          Math.PI / 2,
          0,
          Math.PI / 2,
        ),
      })),
    [],
  );

  const selectedRef = useRef(selectedQuadrant);
  selectedRef.current = selectedQuadrant;

  const handlePress = useCallback(
    (id: Quadrant, e: any) => {
      e.stopPropagation();
      onQuadrantSelect?.(selectedRef.current === id ? null : id);
    },
    [onQuadrantSelect],
  );

  const hasSelection = selectedQuadrant !== null;

  return (
    <group rotation={[0, Math.PI, 0]}>
      {geometries.map((q) => {
        const active = selectedQuadrant === q.id;
        const opacity = !hasSelection ? 0.08 : active ? 0.32 : 0.02;

        return (
          <mesh
            key={q.id}
            geometry={q.geo}
            onClick={(e: any) => handlePress(q.id, e)}
          >
            <meshBasicMaterial
              color={active ? palette.primary : "#FFFFFF"}
              transparent
              opacity={opacity}
              side={THREE.DoubleSide}
              depthWrite={false}
            />
          </mesh>
        );
      })}
    </group>
  );
});

const QuadrantLabels = React.memo(function QuadrantLabels({
  selectedQuadrant,
  palette,
}: {
  selectedQuadrant: Quadrant | null;
  palette: any;
}) {
  const labels = useMemo(
    () =>
      QUADRANTS.map((q) => {
        // Mid-angle of this zone's 90° sweep, matching QuadrantZones exactly.
        const text = QUADRANT_LABEL_TEXT[q.id];
        const texture = buildLabelTexture(text);
        const aspect = texture.image.width / texture.image.height;
        const planeHeight = LABEL_PLANE_HEIGHT;
        const planeWidth = planeHeight * aspect;
        const midPhi = q.phiMid;
        return {
          id: q.id,
          texture,
          planeWidth,
          planeHeight,
          pos: [
            Math.cos(midPhi) * LABEL_RADIUS,
            0,
            -Math.sin(midPhi) * LABEL_RADIUS,
          ] as [number, number, number],
          rotY: -midPhi + Math.PI / 2,
        };
      }),
    [],
  );

  const hasSelection = selectedQuadrant !== null;

  return (
    <group>
      {labels.map((l) => {
        const active = selectedQuadrant === l.id;

        const opacity = !hasSelection ? 0.45 : active ? 1 : 0.18;

        return (
          <mesh key={l.id} position={l.pos} rotation={[-Math.PI / 2, 0, 0]}>
            <planeGeometry args={[l.planeWidth, l.planeHeight]} />
            <meshBasicMaterial
              map={l.texture}
              color={active ? palette.primary : palette.inkFaint}
              transparent
              opacity={opacity}
              depthWrite={false}
              side={THREE.DoubleSide}
              toneMapped={false}
            />
          </mesh>
        );
      })}
    </group>
  );
});

const FindingDots = React.memo(function FindingDots({
  dots,
  visible,
  palette,
  selectedQuadrant,
}: {
  dots: DomeDot[];
  visible: Record<string, boolean>;
  palette: any;
  selectedQuadrant?: Quadrant | null;
}) {
  const points = useMemo(() => dots.filter((d) =>
    d.source === "dmas-cf" && [d.x, d.y, d.z].every(Number.isFinite)
  ), [dots]);
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const color = useMemo(() => new THREE.Color(), []);
  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    points.forEach((dot, i) => {
      dummy.position.set(...toThree(dot));
      dummy.scale.setScalar(0.045);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      const active = !selectedQuadrant || getQuadrantFromArray(dot.x, dot.y) === selectedQuadrant;
      mesh.setColorAt(i, color.set(active ? "#7C3AED" : "#D8C6F5"));
    });
    mesh.count = points.length;
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }, [points, selectedQuadrant, dummy, color]);
  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, Math.max(1, points.length)]} frustumCulled={false}>
      <icosahedronGeometry args={[1, 1]} />
      <meshBasicMaterial />
    </instancedMesh>
  );
});

const AntennaLines = React.memo(function AntennaLines({
  visible,
  antennas,
  palette,
}: {
  visible: boolean;
  antennas: DomeAntenna[];
  palette: any;
}) {

  const SEGMENTS = 8;

  const geometry = useMemo(() => {
    const vertexCount = antennas.length * SEGMENTS * 2; // 2 vertices per line segment
    const positions = new Float32Array(vertexCount * 3);

    let index = 0;
    for (const antenna of antennas) {
      const [ax, , az] = toThree(antenna);
      const phi = Math.atan2(az, ax);

      let prevX = 0;
      let prevY = 0;
      let prevZ = 0;

      for (let i = 0; i <= SEGMENTS; i++) {
        const t = i / SEGMENTS;
        const theta = (Math.PI / 2) * (1 - t);
        const x = DOME_RADIUS * Math.sin(theta) * Math.cos(phi);
        const y = DOME_RADIUS * Math.cos(theta);
        const z = DOME_RADIUS * Math.sin(theta) * Math.sin(phi);
        if (i > 0) {
          positions[index++] = prevX;
          positions[index++] = prevY;
          positions[index++] = prevZ;

          positions[index++] = x;
          positions[index++] = y;
          positions[index++] = z;
        }

        prevX = x;
        prevY = y;
        prevZ = z;
      }
    }

    const geometry = new THREE.BufferGeometry();

    geometry.setAttribute(
      "position",
      new THREE.BufferAttribute(positions, 3)
    );
    geometry.computeBoundingSphere();
    return geometry;
  }, [antennas]);


  const material = useMemo(
    () =>
      new THREE.LineBasicMaterial({
        color: palette.brand,
        transparent: true,
        opacity: 0.3,
      }),
    [palette.brand]
  );

  useEffect(() => {
    return () => {
      geometry.dispose();
      material.dispose();
    };
  }, [geometry, material]);

  return (
    <lineSegments visible={visible} geometry={geometry} material={material} />
  );
});

const AntennaMarkers = React.memo(function AntennaMarkers({
  antennas,
  showAntennas,
  activeIds,
  palette,
}: {
  antennas: DomeAntenna[];
  showAntennas: boolean;
  activeIds: string[];
  palette: any;
}) {
  const activeSet = useMemo(() => new Set(activeIds), [activeIds]);

  const geometry = useMemo(
    () => new THREE.IcosahedronGeometry(1, 1),
    []
  );

  const materials = useMemo(
    () => ({
      active: new THREE.MeshStandardMaterial({
        color: palette.brandDark,
        emissive: palette.brandDark,
        emissiveIntensity: 0.5,
        roughness: 0.4,
      }),

      inactive: new THREE.MeshStandardMaterial({
        color: palette.lavenderDark,
        roughness: 0.4,
      }),

      pulse: new THREE.MeshBasicMaterial({
        color: palette.brandDark,
        transparent: true,
        opacity: 0.8,
      }),
    }),
    [palette.brandDark, palette.lavenderDark]
  );

  const pulseMeshes = useRef<Record<string, THREE.Mesh>>({});
  const pulseTime = useRef(0);

  const placed = useMemo(
    () =>
      antennas.map((a) => ({
        id: a.id,
        position: toThree(a),
      })),
    [antennas]
  );

  useFrame((_, delta) => {
    const meshes = pulseMeshes.current;
    const ids = Object.keys(meshes);

    if (ids.length === 0) return;

    pulseTime.current = (pulseTime.current + delta * 0.5) % 1;

    const scale = 0.07 + pulseTime.current * 0.16;

    materials.pulse.opacity = 0.8 * (1 - pulseTime.current);

    for (let i = 0; i < ids.length; i++) {
      meshes[ids[i]].scale.setScalar(scale);
    }
  });

  useEffect(() => {
    return () => {
      geometry.dispose();
      materials.active.dispose();
      materials.inactive.dispose();
      materials.pulse.dispose();
    };
  }, [geometry, materials]);

  if (!showAntennas) return null;

  return (
    <>
      {placed.map((a) => {
        const active = activeSet.has(a.id);

        return (
          <React.Fragment key={a.id}>
            {active && (
              <mesh
                ref={(mesh) => {
                  if (mesh) {
                    pulseMeshes.current[a.id] = mesh;
                  } else {
                    delete pulseMeshes.current[a.id];
                  }
                }}
                position={a.position}
                geometry={geometry}
                material={materials.pulse}
              />
            )}

            <mesh
              position={a.position}
              scale={active ? 0.06 : 0.04}
              geometry={geometry}
              material={
                active
                  ? materials.active
                  : materials.inactive
              }
            />
          </React.Fragment>
        );
      })}
    </>
  );
});

const Beams = React.memo(function Beams({
  visible,
  antennas,
  activeIds,
  palette,
}: {
  visible: boolean;
  antennas: DomeAntenna[];
  activeIds: string[];
  palette: any;
}) {

  const segments = useMemo(() => {
    const activeSet = new Set(activeIds);
    const activeAnts = antennas.filter((a) => activeSet.has(a.id));

    if (activeAnts.length === 0 || antennas.length <= 4) return [];
    const src = toThree(activeAnts[0]);
    const out: { key: string; geo: THREE.TubeGeometry }[] = [];
    antennas.forEach((t, j) => {
      if (j % 7 !== 0 || t.id === activeAnts[0].id) return;
      const tp = toThree(t);
      const curve = new THREE.CatmullRomCurve3([
        new THREE.Vector3(...src),
        new THREE.Vector3(...tp),
      ]);
      out.push({
        key: `b-${t.id}`,
        geo: new THREE.TubeGeometry(curve, 1, 0.005, 6, false),
      });
    });
    return out;
  }, [antennas, activeIds]);

  useEffect(() => {
    return () => {
      segments.forEach(({ geo }) => geo.dispose());
    };
  }, []);


  const material = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: palette.brandDark,
        transparent: true,
        opacity: 0.3,
      }),
    [palette.brandDark]
  );

  return (
    <group visible={visible} >
      {segments.map((s) => (
        <mesh key={s.key} geometry={s.geo} dispose={null} material={material} />
      ))}
    </group>
  );
});

function DomeScene({
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
  onQuadrantSelect,
  selectedQuadrant = null,
  loading = false,
  error = null,
  cameraPosition = [0, 2.0, 4.2],
  snapshotActionRef,
}: Props) {
  const { theme } = useAppTheme();
  const palette = usePalette(theme);

  const handleQuadrantSelect = useCallback(
    (q: Quadrant | null) => onQuadrantSelect?.(q),
    [onQuadrantSelect],
  );

  if (
    !size ||
    size <= 0 ||
    (!loading && !error && antennas.length === 0 && dots.length === 0)
  ) {
    return (
      <CenteredMessage size={size || 1}>
        <ActivityIndicator color={palette.primary} />
      </CenteredMessage>
    );
  }

  if (error) {
    const { Text } = require("react-native");
    return (
      <CenteredMessage size={size}>
        <Text style={{ color: palette.inkFaint, fontSize: 13 }}>
          {`Unable to load dome view: ${error}`}
        </Text>
      </CenteredMessage>
    );
  }

  if (loading) {
    const { ActivityIndicator } = require("react-native");
    return (
      <CenteredMessage size={size}>
        <ActivityIndicator color={palette.primary} />
      </CenteredMessage>
    );
  }

  return (
    <Canvas
      onCreated={({ gl }) => {
        // if (gl.setPixelRatio) {
        //   gl.setPixelRatio(1);
        // }
      }}
      testID={testID}
      camera={{ position: cameraPosition, fov: 45 }}
      gl={{
        antialias: true,
        alpha: true,
        powerPreference: "high-performance",
        preserveDrawingBuffer: false,
      }}
      // dpr={[1, 1.5]}
      style={{ width: size, height: size, backgroundColor: "transparent" }}
    >
      <ambientLight intensity={0.55} />
      <directionalLight
        position={[4, 10, 4]}
        intensity={1.1}
        castShadow={false}
      // shadow-mapSize-width={512}
      // shadow-mapSize-height={512}
      // shadow-camera-far={15}
      // shadow-camera-left={-6}
      // shadow-camera-right={6}
      // shadow-camera-top={6}
      // shadow-camera-bottom={-6}
      />
      <directionalLight
        position={[-4, 6, -4]}
        intensity={0.3}
        color={palette.lavenderFallback}
      />
      <pointLight
        position={[0, 3, -2.5]}
        intensity={0.35}
        color={palette.brandDarkFallbackPink}
      />

      <Suspense fallback={null}>
        <HemisphereMesh palette={palette} selectedQuadrant={selectedQuadrant} />
        <LatitudeRings palette={palette} selectedQuadrant={selectedQuadrant} />
        {/* <Meridians antennas={antennas} palette={palette} /> */}
        <BaseRing palette={palette} />

        <QuadrantZones
          onQuadrantSelect={handleQuadrantSelect}
          selectedQuadrant={selectedQuadrant}
          palette={palette}
        />
        <QuadrantLabels selectedQuadrant={selectedQuadrant} palette={palette} />

        <AntennaLines visible={!loading} antennas={antennas} palette={palette} />

        <FindingDots
          dots={dots}
          visible={visible}
          palette={palette}
          selectedQuadrant={selectedQuadrant}
        />

        <AntennaMarkers
          antennas={antennas}
          showAntennas={showAntennas}
          activeIds={activeIds}
          // pulsePhase={pulsePhase}
          palette={palette}
        />

        <Beams visible={showBeams} antennas={antennas} activeIds={activeIds} palette={palette} />

        {/* apex / nipple reference marker, at dome z=1 -> three.y = DOME_RADIUS */}
        <mesh position={[0, DOME_RADIUS, 0]}>
          <sphereGeometry args={[0.09, 24, 24]} />
          <meshStandardMaterial
            color={palette.apexColor}
            emissive={palette.apexEmissive}
            emissiveIntensity={1.2}
            roughness={0.5}
          />
        </mesh>
      </Suspense>

      <OrbitControls
        enabled={interactive}
        enablePan={false}
        enableZoom={false}
        enableDamping
        autoRotate={false}
        dampingFactor={0.1}
        minDistance={7}
        maxDistance={12}
        minPolarAngle={0.05}
        maxPolarAngle={Math.PI / 2 - 0.05}
        zoomSpeed={0.6}
        rotateSpeed={0.5}
      />
      {snapshotActionRef && <SnapshotTrigger triggerRef={snapshotActionRef} />}
    </Canvas>
  );
}

export default React.memo(DomeScene, (prev, next) => {
  return (
    prev.size === next.size &&
    prev.dots === next.dots &&
    prev.antennas === next.antennas &&
    prev.visible === next.visible &&
    prev.showAntennas === next.showAntennas &&
    prev.showBeams === next.showBeams &&
    prev.pulsePhase === next.pulsePhase &&
    prev.selectedQuadrant === next.selectedQuadrant &&
    prev.activeIds === next.activeIds
  );
});
