import { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Line, Text } from "@react-three/drei";
import type { UnknownRecord, ServiceState } from "../lib/api";

const COLOR: Record<ServiceState, { color: string; emissive: string }> = {
  ok: { color: "#66c89b", emissive: "#1d4a36" },
  anomaly: { color: "#e7bd69", emissive: "#5a4513" },
  down: { color: "#e47d7d", emissive: "#6a1f1f" },
  unknown: { color: "#72d7e5", emissive: "#153942" },
};
const reduced = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** A dependency edge; dashes drift slowly only while an incident is open (and motion is allowed). */
function Edge({ from, to, animate }: { from: [number, number, number]; to: [number, number, number]; animate: boolean }) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ref = useRef<any>(null);
  useFrame((_, delta) => {
    if (animate && ref.current?.material) ref.current.material.dashOffset -= delta * 0.6;
  });
  return (
    <Line ref={ref} points={[from, to]} color={animate ? "#72d7e5" : "#40515d"} lineWidth={animate ? 1.6 : 1}
      dashed={animate} dashSize={0.18} gapSize={0.12} />
  );
}

function Graph({ names, links, states, root, animate }: {
  names: string[]; links: [string, string][]; states: Record<string, ServiceState>; root?: string; animate: boolean;
}) {
  const points = names.map((name, i) => {
    const angle = (i / Math.max(1, names.length)) * Math.PI * 2;
    return { name, position: [Math.cos(angle) * 2.1, Math.sin(angle) * 1.25, 0] as [number, number, number] };
  });
  const get = (name: string) => points.find((p) => p.name === name)?.position;
  return (
    <>
      {links.map(([a, b], i) => {
        const from = get(a), to = get(b);
        return from && to ? <Edge key={i} from={from} to={to} animate={animate} /> : null;
      })}
      {points.map(({ name, position }) => {
        const isRoot = root === name;
        const c = isRoot ? COLOR.down : COLOR[states[name] ?? "unknown"];
        return (
          <group key={name} position={position}>
            <mesh>
              <sphereGeometry args={[isRoot ? 0.24 : 0.19, 24, 18]} />
              <meshStandardMaterial color={c.color} emissive={c.emissive} emissiveIntensity={isRoot ? 1.4 : 0.9} />
            </mesh>
            <mesh>
              <sphereGeometry args={[isRoot ? 0.36 : 0.28, 24, 18]} />
              <meshBasicMaterial color={c.color} transparent opacity={0.12} />
            </mesh>
            <Text position={[0, -0.42, 0]} fontSize={0.14} color="#dbe4eb" anchorX="center">
              {name}
            </Text>
            {isRoot && (
              <Text position={[0, 0.46, 0]} fontSize={0.12} color="#e47d7d" anchorX="center">
                root cause
              </Text>
            )}
          </group>
        );
      })}
      <ambientLight intensity={1.0} />
      <pointLight position={[0, 0, 4]} intensity={18} />
      <OrbitControls enablePan={false} enableZoom={false} enableRotate={false} />
    </>
  );
}

export default function ThreeMap({ names, topology, states = {}, root, incidentOpen = false }: {
  names: string[]; topology: UnknownRecord; states?: Record<string, ServiceState>; root?: string; incidentOpen?: boolean;
}) {
  const links: [string, string][] = [];
  Object.entries(topology).forEach(([a, raw]) => {
    if (Array.isArray(raw)) raw.forEach((b) => { if (typeof b === "string") links.push([a, b]); });
  });
  return (
    <div className="three-wrap" aria-label="Three dimensional view of returned services, coloured by live health">
      <Canvas dpr={[1, 1.4]} camera={{ position: [0, 0, 6], fov: 42 }}>
        <Graph names={names} links={links} states={states} root={root} animate={incidentOpen && !reduced()} />
      </Canvas>
    </div>
  );
}
