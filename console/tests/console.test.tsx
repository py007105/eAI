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
    expect(screen.getAllByText("0")).toHaveLength(2);
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
    await waitFor(() =>
      expect(screen.getByText("Returned evidence")).toBeInTheDocument(),
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
