import {
  createContext,
  createElement,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  fetchTelemetry,
  isRecord,
  numberValue,
  validPayload,
  type EndpointKey,
  type EndpointState,
  type Telemetry,
} from "./api";
import { appendSample, type Sample } from "./history";
const keys: EndpointKey[] = [
  "status",
  "services",
  "incidents",
  "approvals",
  "audit",
];
const empty = Object.fromEntries(
  keys.map((key) => [key, { loading: true }]),
) as Telemetry;
export function isFresh(
  updatedAt: number | undefined,
  now: number,
  threshold = 6000,
): boolean {
  return (
    updatedAt !== undefined &&
    Number.isFinite(updatedAt) &&
    now - updatedAt < threshold
  );
}
export function deriveConnection(data: Telemetry, now: number) {
  const required: EndpointKey[] = [
    "status",
    "services",
    "incidents",
    "approvals",
    "audit",
  ];
  const successes = required.filter(
    (k) => isFresh(data[k].updatedAt, now) && !data[k].error,
  ).length;
  const latest = Math.max(0, ...required.map((k) => data[k].updatedAt ?? 0));
  const age = latest
    ? Math.max(0, Math.floor((now - latest) / 1000))
    : undefined;
  const settled = required.every((k) => !data[k].loading);
  const connection: "connecting" | "disconnected" | "live" | "partial" = !latest
    ? settled
      ? "disconnected"
      : "connecting"
    : age! >= 6
      ? "disconnected"
      : successes === required.length
        ? "live"
        : "partial";
  return { connection, age };
}
const TelemetryContext = createContext<{
  data: Telemetry;
  samples: Record<string, Sample[]>;
  connection: "connecting" | "live" | "partial" | "disconnected";
  age?: number;
}>({ data: empty, samples: {}, connection: "connecting" });
export function TelemetryProvider({ children }: { children: React.ReactNode }) {
  const [data, setData] = useState<Telemetry>(empty);
  const [samples, setSamples] = useState<Record<string, Sample[]>>({});
  const [now, setNow] = useState(Date.now());
  const busy = useRef(false);
  useEffect(() => {
    let timer: number | undefined;
    let active = true;
    const poll = async () => {
      if (!active || document.hidden || busy.current) return;
      busy.current = true;
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 5000);
      try {
        const result = await fetchTelemetry(controller.signal);
        const stamp = Date.now();
        const servicePayload = result.services;
        setSamples((previous) => {
          const validServices = validPayload("services", servicePayload)
            ? (servicePayload as { services: Record<string, unknown> }).services
            : undefined;
          const names = new Set([
            ...Object.keys(previous),
            ...Object.keys(validServices ?? {}),
          ]);
          return Object.fromEntries(
            [...names].slice(-64).map((name) => {
              const snapshot = validServices?.[name];
              const score = isRecord(snapshot)
                ? numberValue(snapshot.score)
                : undefined;
              return [
                name,
                appendSample(previous[name] ?? [], score, stamp, 60),
              ];
            }),
          );
        });
        setData(
          (prev) =>
            Object.fromEntries(
              keys.map((key) => {
                const value = result[key];
                if (value && typeof value === "object" && "__error" in value)
                  return [
                    key,
                    {
                      ...prev[key],
                      loading: false,
                      error: String((value as { __error: unknown }).__error),
                    } satisfies EndpointState,
                  ];
                if (!validPayload(key, value))
                  return [
                    key,
                    {
                      ...prev[key],
                      loading: false,
                      error: "Unexpected response schema",
                    } satisfies EndpointState,
                  ];
                return [
                  key,
                  {
                    value,
                    updatedAt: stamp,
                    loading: false,
                  } satisfies EndpointState,
                ];
              }),
            ) as Telemetry,
        );
      } finally {
        window.clearTimeout(timeout);
        busy.current = false;
      }
    };
    const tick = () => {
      void poll();
      timer = window.setTimeout(tick, 2000);
    };
    const visible = () => {
      if (!document.hidden) void poll();
    };
    void poll();
    timer = window.setTimeout(tick, 2000);
    document.addEventListener("visibilitychange", visible);
    const clock = window.setInterval(() => setNow(Date.now()), 1000);
    return () => {
      active = false;
      if (timer) window.clearTimeout(timer);
      window.clearInterval(clock);
      document.removeEventListener("visibilitychange", visible);
    };
  }, []);
  const value = useMemo(() => {
    const { connection, age } = deriveConnection(data, now);
    return { data, samples, connection, age };
  }, [data, samples, now]);
  return createElement(TelemetryContext.Provider, { value }, children);
}
export const useTelemetry = () => useContext(TelemetryContext);
