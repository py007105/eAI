import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "./server";
import { App } from "../src/App";
import { currentTelemetry } from "../src/lib/useTelemetry";
import type { Telemetry } from "../src/lib/api";
import { incidentDurations } from "../src/lib/charts";
import NumberTicker from "../src/components/NumberTicker";
import { RecoveryProof } from "../src/pages/LiveIncident";

const incident = {
  id: "review-1", opened_t: 100, status: "verifying", likely_cause: "down",
  services: ["web"], ranking: [{ service: "web", score: 0.98 }],
  actions: [{ verdict: "execute", executed: true, runbook_id: "restart_service", t: 108, executed_t: 112 }],
  evidence: Array.from({ length: 6 }, (_, i) => ({ id: `ev${i}`, tool: "metrics", summary: `Evidence item ${i}` })),
  report: { summary: "Observed web interruption" },
  before: { checkout_success: 0, error_ratio: 0.3, p95_s: 1.2 },
};
afterEach(() => { cleanup(); history.replaceState({}, "", "/"); });
function openLive() {
  server.use(http.get("http://localhost/api/incidents", () => HttpResponse.json([incident])));
  history.replaceState({}, "", "/console/live");
  render(<App />);
}
describe("presentation and data integrity", () => {
  it("independently suppresses failed, expired, and never-loaded endpoint values", () => {
    const data = Object.fromEntries(["status", "services", "incidents", "approvals", "audit"].map((key) => [key, { value: key, updatedAt: 1000, loading: false }])) as Telemetry;
    data.services.error = "503";
    data.audit.updatedAt = -6000;
    data.approvals.updatedAt = undefined;
    const current = currentTelemetry(data, 2000);
    expect(current.status.value).toBe("status");
    expect(current.incidents.value).toBe("incidents");
    expect(current.services.value).toBeUndefined();
    expect(current.audit.value).toBeUndefined();
    expect(current.approvals.value).toBeUndefined();
    expect(data.services.value).toBe("services");
  });
  it("shows exact counts immediately, including transitions to unavailable", () => {
    const view = render(<NumberTicker value="100" />);
    view.rerender(<NumberTicker value="3" />);
    expect(screen.getByText("3")).toBeInTheDocument();
    view.rerender(<NumberTicker value="Unavailable" />);
    expect(screen.queryByText("3")).not.toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
  });
  it("does not label a partial verification as verified recovery duration", () => {
    expect(incidentDurations([{ ...incident, verification: { t: 150, outcome: "partially_recovered" } }])[0].verified_s).toBeNull();
  });
  it("renders measured before/after values with units, and preserves unknowns", () => {
    render(<RecoveryProof inc={incident} />);
    expect(screen.getByText("0.0%")).toBeInTheDocument();
    expect(screen.getByText("30.0%")).toBeInTheDocument();
    expect(screen.getByText("1200 ms")).toBeInTheDocument();
    expect(screen.getByText("Awaiting verification")).toBeInTheDocument();
    expect(screen.getAllByText("Not reported")).toHaveLength(5);
  });
  it("lets the presenter inspect stages and all evidence items", async () => {
    openLive();
    await screen.findByText("Observed web interruption");
    fireEvent.click(screen.getByRole("button", { name: "Inspect Fix executed" }));
    expect(screen.getByText("Fix executed · done")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Evidence", { selector: "summary" }));
    expect(screen.getByText("Evidence item 5")).toBeVisible();
    expect(screen.getByRole("link", { name: "Full investigation" })).toHaveAttribute("href", "/console/incidents/review-1");
  });
  it("keeps a selected incident and focus view reversible", async () => {
    openLive();
    await screen.findByText("Observed web interruption");
    fireEvent.change(screen.getByRole("combobox", { name: "Choose incident" }), { target: { value: "review-1" } });
    expect(screen.getByText("Following the selected incident as it updates.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Focus view" }));
    expect(document.querySelector(".focus-layout")).not.toBeNull();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(document.querySelector(".focus-layout")).toBeNull();
  });
  it("suppresses stale incident content on partial failure, then resumes the same selection", async () => {
    openLive();
    await screen.findByText("Observed web interruption");
    fireEvent.change(screen.getByRole("combobox", { name: "Choose incident" }), { target: { value: "review-1" } });
    server.use(http.get("http://localhost/api/incidents", () => new HttpResponse(null, { status: 503 })));
    await screen.findByText("Live incident view unavailable", {}, { timeout: 4000 });
    expect(screen.queryByText("Observed web interruption")).not.toBeInTheDocument();
    expect(screen.getByText("Partial data")).toBeInTheDocument();
    server.use(http.get("http://localhost/api/incidents", () => HttpResponse.json([incident])));
    await screen.findByText("Observed web interruption", {}, { timeout: 4000 });
    expect(screen.getByRole("combobox", { name: "Choose incident" })).toHaveValue("review-1");
  }, 10000);
  it("does not call the highest ranked service a cause after abstention", async () => {
    server.use(http.get("http://localhost/api/incidents", () => HttpResponse.json([{ ...incident, abstained: true }])));
    history.replaceState({}, "", "/console/live");
    render(<App />);
    expect(await screen.findByText("Abstained · insufficient evidence")).toBeInTheDocument();
  });
  it("removes stale landing KPIs without hiding healthy endpoints", async () => {
    render(<App />);
    const kpis = screen.getByLabelText("Live key figures");
    await within(kpis).findByText("watch-only");
    server.use(http.get("http://localhost/api/status", () => new HttpResponse(null, { status: 503 })));
    await waitFor(() => expect(within(kpis).queryByText("watch-only")).not.toBeInTheDocument(), { timeout: 4000 });
    expect(within(kpis).getByText("1 / 2")).toBeInTheDocument();
  });
});
