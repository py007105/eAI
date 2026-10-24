import {
  fireEvent,
  render,
  screen,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { App } from "../src/App";
import { server } from "./server";

afterEach(() => {
  cleanup();
  history.replaceState({}, "", "/");
});
const incident = {
  id: "inc-1",
  opened_t: 1750000000,
  kind: "reactive",
  status: "open",
  services: ["payments"],
  likely_cause: "memory_leak",
  confidence: 0.91,
  evidence: [
    {
      id: "ev-1",
      tool: "telemetry",
      service: "payments",
      summary: "Returned evidence",
    },
  ],
  actions: [
    {
      runbook_id: "restart_service",
      verdict: "needs_approval",
      status: "proposed",
    },
  ],
  timeline: [{ t: 1750000000, msg: "Observed issue" }],
  verification: null,
  report: { summary: "Reported incident" },
};
function reportIncident() {
  server.use(
    http.get("http://localhost/api/incidents", () =>
      HttpResponse.json([incident]),
    ),
  );
  history.replaceState({}, "", "/console/incidents/inc-1");
}
describe("read-only console screens", () => {
  it("suppresses recently retained values on failed polling and recovers", async () => {
    history.replaceState({}, "", "/console");
    render(<App />);
    await screen.findByText("Score 0");
    server.use(
      http.get(
        "http://localhost/api/services",
        () => new HttpResponse(null, { status: 503 }),
      ),
    );
    await waitFor(
      () => expect(screen.queryByText("Score 0")).not.toBeInTheDocument(),
      { timeout: 4000 },
    );
    expect(screen.getByText("Partial data")).toBeInTheDocument();
    server.resetHandlers();
    await screen.findByText("Score 0", {}, { timeout: 4000 });
  });
  it("serves API fixtures from the test-only MSW server", async () => {
    const response = await fetch("/api/status");
    expect(response.ok).toBe(true);
    expect(await response.json()).toHaveProperty("mode", "watch-only");
  });
  it("renders the landing page and architecture illustration", () => {
    render(<App />);
    expect(
      screen.getByRole("heading", {
        name: "Understand the failure. Inspect the response.",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /architecture illustration/i }),
    ).toBeInTheDocument();
  });
  it("opens Overview and keeps reported zero distinct from a missing score", async () => {
    render(<App />);
    fireEvent.click(screen.getAllByRole("link", { name: /open console/i })[0]);
    await screen.findByRole("heading", { name: "Overview" });
    await waitFor(() =>
      expect(screen.getAllByText("watch-only").length).toBeGreaterThan(0),
    );
    // the two reported zeros in the metric cards (open incidents, pending approvals); other panels may show 0 too
    const metricZeros = [...document.querySelectorAll(".metric-grid .metric-value")].filter((e) => e.textContent?.trim() === "0");
    expect(metricZeros).toHaveLength(2);
    expect(screen.getByText("Score 0")).toBeInTheDocument();
    expect(screen.getByText("No score reported")).toBeInTheDocument();
  });
  it("renders recorded results as readable text while preserving the qualifiers", async () => {
    render(<App />);
    fireEvent.click(
      screen.getByRole("link", { name: "View Verified Results" }),
    );
    await screen.findByRole("heading", { name: "Verified Results" });
    expect(
      await screen.findByText(/18 of 18 supported faults recovered/),
    ).toBeInTheDocument();
    expect(screen.getByText(/simulated operator/)).toBeInTheDocument();
    expect(screen.queryByText(/^\*\*/)).not.toBeInTheDocument();
  });
  it("hides incident confidence when the API calibration flag is false", async () => {
    reportIncident();
    render(<App />);
    await screen.findByRole("heading", { name: "Incident detail" });
    // the evidence summary appears in the evidence list and in the investigation trace
    await waitFor(() =>
      expect(screen.getAllByText("Returned evidence").length).toBeGreaterThan(0),
    );
    expect(screen.queryByText("Confidence 91%")).not.toBeInTheDocument();
  });
  it("shows incident confidence only when the API calibration flag allows it", async () => {
    reportIncident();
    server.use(
      http.get("http://localhost/api/status", () =>
        HttpResponse.json({
          mode: "watch-only",
          calibration: { show_probability: true },
        }),
      ),
    );
    render(<App />);
    await screen.findByRole("heading", { name: "Incident detail" });
    expect(await screen.findByText("Confidence 91%")).toBeInTheDocument();
  });
});
