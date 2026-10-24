import { Canvas } from "@react-three/fiber";
import { OrbitControls, Line, Text } from "@react-three/drei";
import type { UnknownRecord } from "../lib/api";
function Graph({
  names,
  links,
}: {
  names: string[];
  links: [string, string][];
}) {
  const points = names.map((name, i) => {
    const angle = (i / Math.max(1, names.length)) * Math.PI * 2;
    return {
      name,
      position: [Math.cos(angle) * 2.1, Math.sin(angle) * 1.25, 0] as [
        number,
        number,
        number,
      ],
    };
  });
  const get = (name: string) => points.find((p) => p.name === name)?.position;
  return (
    <>
      {links.map(([a, b], i) => {
        const from = get(a),
          to = get(b);
        return from && to ? (
          <Line key={i} points={[from, to]} color="#40515d" lineWidth={1} />
        ) : null;
      })}
      {points.map(({ name, position }) => (
        <group key={name} position={position}>
          <mesh>
            <sphereGeometry args={[0.12, 16, 12]} />
            <meshStandardMaterial color="#72d7e5" emissive="#153942" />
          </mesh>
          <Text
            position={[0, -0.28, 0]}
            fontSize={0.13}
            color="#dbe4eb"
            anchorX="center"
          >
            {name}
          </Text>
        </group>
      ))}
      <ambientLight intensity={1.2} />
      <OrbitControls
        enablePan={false}
        enableZoom={false}
        enableRotate={false}
      />
    </>
  );
}
export default function ThreeMap({
  names,
  topology,
}: {
  names: string[];
  topology: UnknownRecord;
}) {
  const links: [string, string][] = [];
  Object.entries(topology).forEach(([a, raw]) => {
    if (Array.isArray(raw))
      raw.forEach((b) => {
        if (typeof b === "string") links.push([a, b]);
      });
  });
  return (
    <div
      className="three-wrap"
      aria-label="Three dimensional view of returned services"
    >
      <Canvas dpr={[1, 1.4]} camera={{ position: [0, 0, 6], fov: 42 }}>
        <Graph names={names} links={links} />
      </Canvas>
    </div>
  );
}
