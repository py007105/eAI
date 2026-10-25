import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "./server";
import EvaluatorRun from "../src/components/EvaluatorRun";
afterEach(cleanup);
function start() {
  render(<EvaluatorRun />);
  fireEvent.change(screen.getByLabelText("Evaluator run ID"), { target: { value: "run1" } });
  fireEvent.click(screen.getByRole("button", { name: "Check run" }));
}
it("keeps ground truth hidden until the evaluator says finished", async () => {
  let finished = false;
  server.use(http.get("http://localhost/api/challenge/run1/status", () => HttpResponse.json({ run_id: "run1", state: finished ? "finished" : "running", elapsed_s: 12 })));
  start();
  await screen.findByText(/ground truth remains hidden/);
  expect(screen.queryByRole("button", { name: "Reveal result" })).not.toBeInTheDocument();
  finished = true;
  fireEvent.click(screen.getByRole("button", { name: "Check run" }));
  await screen.findByRole("button", { name: "Reveal result" });
});
it("reveals real result fields, preserves missing fields, clears result when ID changes", async () => {
  server.use(
    http.get("http://localhost/api/challenge/run1/status", () => HttpResponse.json({ run_id: "run1", state: "finished" })),
    http.get("http://localhost/api/challenge/run1/reveal", () => HttpResponse.json({ truth: { run_id: "run1", scenario: "crash", target: "web" }, score: { detected: true, recovered: false, failed_request_pct: 0 } })),
  );
  start();
  fireEvent.click(await screen.findByRole("button", { name: "Reveal result" }));
  await screen.findByRole("heading", { name: "crash · web" });
  expect(screen.getByText("0%")).toBeInTheDocument();
  expect(screen.getAllByText("Not reported").length).toBeGreaterThan(0);
  fireEvent.change(screen.getByLabelText("Evaluator run ID"), { target: { value: "run2" } });
  expect(screen.queryByRole("heading", { name: "crash · web" })).not.toBeInTheDocument();
});
it("rejects an error object returned as HTTP 200 by the status proxy", async () => {
  server.use(http.get("http://localhost/api/challenge/run1/status", () => HttpResponse.json({ detail: "Not found" })));
  start();
  expect(await screen.findByRole("alert")).toHaveTextContent("Unexpected status");
  expect(screen.queryByRole("button", { name: "Reveal result" })).not.toBeInTheDocument();
});
