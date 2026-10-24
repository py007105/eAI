export type UnknownRecord = Record<string, unknown>;
export type EndpointKey =
  | "status"
  | "services"
  | "incidents"
  | "approvals"
  | "audit";
export interface EndpointState<T = unknown> {
  value?: T;
  updatedAt?: number;
  error?: string;
  loading: boolean;
}
export type Telemetry = Record<EndpointKey, EndpointState>;
const endpoints: EndpointKey[] = [
  "status",
  "services",
  "incidents",
  "approvals",
  "audit",
];
export const isRecord = (value: unknown): value is UnknownRecord =>
  !!value && typeof value === "object" && !Array.isArray(value);
export const textValue = (value: unknown): string | undefined =>
  typeof value === "string" && value.trim() ? value.trim() : undefined;
export const numberValue = (value: unknown): number | undefined =>
  typeof value === "number" && Number.isFinite(value) ? value : undefined;
export interface StatusModel {
  mode?: string;
  killSwitch?: boolean;
  openIncidents?: number;
  protectedServices?: string[];
  policy?: UnknownRecord;
  showProbability: boolean;
}
export interface ServiceModel {
  name: string;
  score?: number;
  anomalous?: boolean;
  running?: boolean;
  features?: UnknownRecord;
  raw: UnknownRecord;
}
export interface IncidentModel {
  id?: string;
  openedAt?: number;
  status?: string;
  kind?: string;
  services?: string[];
  likelyCause?: string;
  confidence?: number;
  raw: UnknownRecord;
}
export function adaptStatus(value: unknown): StatusModel | undefined {
  if (!isRecord(value)) return undefined;
  return {
    mode: textValue(value.mode),
    killSwitch:
      typeof value.kill_switch === "boolean" ? value.kill_switch : undefined,
    openIncidents: numberValue(value.open_incidents),
    protectedServices:
      Array.isArray(value.protected_services) &&
      value.protected_services.every((item) => typeof item === "string")
        ? value.protected_services
        : undefined,
    policy: isRecord(value.policy) ? value.policy : undefined,
    showProbability: supportsConfidence(value),
  };
}
export function adaptService(
  name: string,
  value: unknown,
): ServiceModel | undefined {
  if (!isRecord(value)) return undefined;
  const state = isRecord(value.state) ? value.state : undefined;
  return {
    name,
    score: numberValue(value.score),
    anomalous:
      typeof value.anomalous === "boolean" ? value.anomalous : undefined,
    running: typeof state?.running === "boolean" ? state.running : undefined,
    features: isRecord(value.features) ? value.features : undefined,
    raw: value,
  };
}
export function adaptServices(value: unknown): ServiceModel[] | undefined {
  if (!validPayload("services", value)) return undefined;
  const raw = value as { services: Record<string, unknown> };
  const adapted = Object.entries(raw.services).map(([name, snapshot]) =>
    adaptService(name, snapshot),
  );
  return adapted.every((service) => service !== undefined)
    ? (adapted as ServiceModel[])
    : undefined;
}
export function adaptIncident(value: UnknownRecord): IncidentModel {
  return {
    id: textValue(value.id),
    openedAt: numberValue(value.opened_t),
    status: textValue(value.status),
    kind: textValue(value.kind),
    services:
      Array.isArray(value.services) &&
      value.services.every((item) => typeof item === "string")
        ? value.services
        : undefined,
    likelyCause: textValue(value.likely_cause),
    confidence: numberValue(value.confidence),
    raw: value,
  };
}
export function adaptIncidents(value: unknown): IncidentModel[] | undefined {
  const rows = parseArray(value);
  return rows?.map(adaptIncident);
}
export const endpointPath = (key: EndpointKey) => `/api/${key}`;
async function getJson(path: string, signal: AbortSignal): Promise<unknown> {
  const response = await fetch(path, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json() as Promise<unknown>;
}
export async function fetchTelemetry(signal: AbortSignal) {
  return Object.fromEntries(
    await Promise.all(
      endpoints.map(async (key) => {
        try {
          return [key, await getJson(endpointPath(key), signal)] as const;
        } catch (error) {
          return [
            key,
            {
              __error:
                error instanceof Error ? error.message : "Request failed",
            },
          ] as const;
        }
      }),
    ),
  ) as Record<EndpointKey, unknown>;
}
export function parseArray(value: unknown): UnknownRecord[] | undefined {
  if (!Array.isArray(value) || !value.every(isRecord)) return undefined;
  return value;
}
export function validPayload(key: EndpointKey, value: unknown): boolean {
  if (key === "status") return isRecord(value);
  if (key === "services")
    return (
      isRecord(value) &&
      isRecord(value.services) &&
      Object.values(value.services).every(isRecord) &&
      isRecord(value.topology) &&
      Object.values(value.topology).every(
        (deps) =>
          Array.isArray(deps) &&
          deps.every((service) => typeof service === "string"),
      )
    );
  return parseArray(value) !== undefined;
}
export function parseIncidentId(value: UnknownRecord): string | undefined {
  return textValue(value.id);
}
export function supportsConfidence(status: unknown): boolean {
  return (
    isRecord(status) &&
    isRecord(status.calibration) &&
    status.calibration.show_probability === true
  );
}
export function knownCount(value: unknown): number | undefined {
  return numberValue(value);
}
