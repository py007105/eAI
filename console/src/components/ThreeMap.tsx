import { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Html, OrbitControls, Line } from "@react-three/drei";
import type { UnknownRecord, ServiceState } from "../lib/api";

const COLOR: Record<ServiceState, { color: string; emissive: string }> = {
  ok: { color: "#39ff14", emissive: "#1f8a0b" },
  anomaly: { color: "#f79009", emissive: "#7a4504" },
  down: { color: "#f04438", emissive: "#7a1f18" },
  unknown: { color: "#8a948f", emissive: "#2a302d" },
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
    <Line ref={ref} points={[from, to]} color={animate ? "#39ff14" : "#3a4a40"} lineWidth={animate ? 1.6 : 1}
      dashed={animate} dashSize={0.18} gapSize={0.12} />
  );
}

/** Root-cause halo: pulses slowly (static when reduced motion is requested). */
function Pulse({ color, still }: { color: string; still: boolean }) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ref = useRef<any>(null);
  useFrame(({ clock }) => {
    if (!ref.current || still) return;
    const k = 1 + 0.25 * Math.sin(clock.elapsedTime * 3);
    ref.current.scale.set(k, k, k);
    if (ref.current.material) ref.current.material.opacity = 0.32 - 0.14 * (k - 1) * 4;
  });
  return (
    <mesh ref={ref}>
      <sphereGeometry args={[0.38, 24, 18]} />
      <meshBasicMaterial color={color} transparent opacity={0.28} />
    </mesh>
  );
}

function Graph({ names, links, states, root, animate, selected, onSelect }: {
  names: string[]; links: [string, string][]; states: Record<string, ServiceState>; root?: string; animate: boolean; selected?: string; onSelect?: (name: string) => void;
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
          <group key={name} position={position} onClick={(event) => { event.stopPropagation(); onSelect?.(name); }}>
            <mesh scale={selected === name ? 1.25 : 1}>
              <sphereGeometry args={[isRoot ? 0.24 : 0.19, 24, 18]} />
              <meshStandardMaterial color={c.color} emissive={c.emissive} emissiveIntensity={isRoot ? 1.4 : 0.9} />
            </mesh>
            {isRoot ? (
              <Pulse color={c.color} still={reduced()} />
            ) : (
              <mesh>
                <sphereGeometry args={[0.3, 24, 18]} />
                <meshBasicMaterial color={c.color} transparent opacity={0.16} />
              </mesh>
            )}
            {/* DOM labels: page font, no runtime font download */}
            <Html position={[0, -0.42, 0]} center zIndexRange={[10, 0]}>
              <span className="three-label">{name}</span>
            </Html>
            {isRoot && (
              <Html position={[0, 0.5, 0]} center zIndexRange={[10, 0]}>
                <span className="three-label three-label-root">likely root cause</span>
              </Html>
            )}
          </group>
        );
      })}
      <ambientLight intensity={1.0} />
      <pointLight position={[0, 0, 4]} intensity={18} />
      <OrbitControls enablePan={false} enableZoom={false} enableRotate />
    </>
  );
}

export default function ThreeMap({ names, topology, states = {}, root, incidentOpen = false, selected, onSelect }: {
  names: string[]; topology: UnknownRecord; states?: Record<string, ServiceState>; root?: string; incidentOpen?: boolean; selected?: string; onSelect?: (name: string) => void;
}) {
  const links: [string, string][] = [];
  Object.entries(topology).forEach(([a, raw]) => {
    if (Array.isArray(raw)) raw.forEach((b) => { if (typeof b === "string") links.push([a, b]); });
  });
  return (
    <div className="three-wrap" aria-label="Three dimensional view of returned services, coloured by live health; drag to rotate">
      <Canvas dpr={[1, 1.4]} camera={{ position: [0, 0, 6], fov: 42 }}>
        <Graph selected={selected} onSelect={onSelect} names={names} links={links} states={states} root={root} animate={incidentOpen && !reduced()} />
      </Canvas>
    </div>
  );
}
