import { describe, expect, it, vi } from "vitest";
import { appendSample } from "../src/lib/history";
import { recordedResultsExcerpt } from "../src/lib/results";
import { deriveConnection, isFresh } from "../src/lib/useTelemetry";
import type { Telemetry } from "../src/lib/api";
import {
  adaptIncident,
  adaptIncidents,
  adaptService,
  adaptServices,
  adaptStatus,
  auditResult,
  auditWhat,
  endpointPath,
  fetchTelemetry,
  knownCount,
  parseArray,
  serviceState,
  supportsConfidence,
  validPayload,
} from "../src/lib/api";

// Record shapes as returned by the live demo-stable-1 API on 25 Oct 2026 (GET /audit, GET /services).
describe("audit columns and topology state use the API's own field names", () => {
  const executed = { t: 1, runbook: "restart_service", service: "web", actor: "autopilot", ok: true, result: { restarted: "web" } };
  const verification = { t: 2, kind: "verification", incident_id: "d38555ed", runbook: "restart_service", service: "web", outcome: "recovered", success_rate: 1 };
  it("names the audit action from runbook and service", () => {
    expect(auditWhat(executed)).toBe("restart_service on web");
    expect(auditWhat(verification)).toBe("restart_service on web");
    expect(auditWhat({ action: "approve" })).toBe("approve");
    expect(auditWhat({})).toBeUndefined();
  });
  it("reports the audit result from ok and outcome", () => {
    expect(auditResult(executed)).toBe("ok");
    expect(auditResult({ ...executed, ok: false })).toBe("failed");
    expect(auditResult(verification)).toBe("recovered");
    expect(auditResult({})).toBeUndefined();
  });
  it("derives the topology state only from state.running and anomalous", () => {
    expect(serviceState({ anomalous: false, state: { running: true } })).toBe("ok");
    expect(serviceState({ anomalous: true, state: { running: true } })).toBe("anomaly");
    expect(serviceState({ anomalous: true, state: { running: false } })).toBe("down");
    expect(serviceState({ score: 0.4 })).toBe("unknown");
    expect(serviceState(undefined)).toBe("unknown");
  });
});

describe("API contract adapters", () => {
  it("keeps recorded results source-backed and excludes forbidden presentation wording", () => {
    const text = recordedResultsExcerpt();
    expect(text).not.toMatch(/\\bdemo\\b/i);
    expect(text).toContain("18 of 18 supported faults recovered");
    expect(text).toContain("simulated operator");
    expect(text).toContain("0.385");
    expect(text).toContain("0.449");
  });
  it("keeps absent numeric values unknown and preserves a reported zero", () => {
    expect(knownCount(undefined)).toBeUndefined();
    expect(knownCount(0)).toBe(0);
    expect(knownCount("0")).toBeUndefined();
  });
  it("rejects unexpected array shapes rather than filtering invalid records", () => {
    expect(parseArray([{}])).toEqual([{}]);
    expect(parseArray([null])).toBeUndefined();
    expect(validPayload("status", [])).toBe(false);
    expect(validPayload("services", { services: {}, topology: {} })).toBe(true);
  });
  it("maps supported API fields without turning missing values into zero", () => {
    expect(
      adaptStatus({ mode: "watch-only", open_incidents: 0 })?.openIncidents,
    ).toBe(0);
    expect(adaptStatus({})?.openIncidents).toBeUndefined();
    expect(adaptService("payments", { score: 0 })?.score).toBe(0);
    expect(
      adaptServices({
        services: { payments: { score: 0 } },
        topology: { payments: [] },
      })?.[0]?.name,
    ).toBe("payments");
    expect(adaptIncidents([{ id: "i-1", opened_t: 5 }])?.[0]?.openedAt).toBe(5);
    expect(adaptIncident({ id: "i-2" }).openedAt).toBeUndefined();
  });
  it("shows confidence only when status explicitly permits it", () => {
    expect(
      supportsConfidence({ calibration: { show_probability: true } }),
    ).toBe(true);
    expect(
      supportsConfidence({ calibration: { show_probability: false } }),
    ).toBe(false);
    expect(supportsConfidence({})).toBe(false);
  });
  it("uses only relative /api paths and GET for every request", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await fetchTelemetry(new AbortController().signal);
    expect(spy).toHaveBeenCalledTimes(5);
    for (const call of spy.mock.calls) {
      expect(call[0]).toMatch(/^\/api\//);
      expect((call[1] as RequestInit).method).toBe("GET");
    }
    expect(endpointPath("status")).toBe("/api/status");
  });
  it("marks values historical after the documented stale threshold", () => {
    expect(isFresh(1000, 6999)).toBe(true);
    expect(isFresh(1000, 7000)).toBe(false);
  });
  it("shows connecting, live, partial, disconnected, and recovery states", () => {
    const blank = Object.fromEntries(
      ["status", "services", "incidents", "approvals", "audit"].map((key) => [
        key,
        { loading: true },
      ]),
    ) as Telemetry;
    expect(deriveConnection(blank, 1000).connection).toBe("connecting");
    const failed = Object.fromEntries(
      ["status", "services", "incidents", "approvals", "audit"].map((key) => [
        key,
        { loading: false, error: "offline" },
      ]),
    ) as Telemetry;
    expect(deriveConnection(failed, 1000).connection).toBe("disconnected");
    const live = Object.fromEntries(
      ["status", "services", "incidents", "approvals", "audit"].map((key) => [
        key,
        { value: {}, updatedAt: 1000, loading: false },
      ]),
    ) as Telemetry;
    expect(deriveConnection(live, 2000).connection).toBe("live");
    const lost = Object.fromEntries(
      Object.entries(live).map(([key, value]) => [
        key,
        { ...value, error: "HTTP 503" },
      ]),
    ) as Telemetry;
    expect(deriveConnection(lost, 2000).connection).toBe("disconnected");
    expect(
      deriveConnection(
        { ...live, approvals: { error: "down", loading: false } },
        2000,
      ).connection,
    ).toBe("partial");
    expect(deriveConnection(live, 8000).connection).toBe("disconnected");
    const recovered = Object.fromEntries(
      ["status", "services", "incidents", "approvals", "audit"].map((key) => [
        key,
        { value: {}, updatedAt: 8000, loading: false },
      ]),
    ) as Telemetry;
    expect(deriveConnection(recovered, 8001).connection).toBe("live");
  });
  it("bounds observed samples and preserves outage gaps without interpolation", () => {
    const first = appendSample([], 3, 1, 3);
    const second = appendSample(first, undefined, 2, 3);
    const third = appendSample(second, 5, 3, 3);
    const fourth = appendSample(third, 7, 4, 3);
    expect(fourth).toEqual([
      { at: 2, value: null },
      { at: 3, value: 5 },
      { at: 4, value: 7 },
    ]);
  });
});
