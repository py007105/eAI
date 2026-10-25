import { describe, expect, it } from "vitest";
import { approverChannel, deriveStages, newestActive, recentClosed, reportProvenance } from "../src/lib/pipeline";
import { buildTrace, evidenceSource, outcomeCounts } from "../src/lib/trace";
import { actionsByChannel, actionsByRunbook, incidentDurations, scoreSeries } from "../src/lib/charts";

// Shapes as returned by the live demo-stable-1 API (25 Oct 2026); values shortened.
const autopilotRecovered = {
  id: "d38555ed", opened_t: 100, closed_t: 151, status: "recovered", services: ["web"], likely_cause: "down",
  abstained: false, ranking: [{ service: "web", score: 0.98 }, { service: "payments", score: 0.01 }],
  actions: [{ t: 107, runbook_id: "restart_service", service: "web", verdict: "execute", risk: "low",
    reason: "autopilot: low-risk runbook allowed by the rulebook", executed: true, approved_by: null, executed_t: 115 }],
  verification: { outcome: "recovered", probes: 19, success_rate: 1, t: 151 },
  evidence: [{ id: "ev1", tool: "metrics", service: "web", summary: "web window metrics" },
    { id: "ev2", tool: "container", service: "web", summary: "web container exited" },
    { id: "ev6", tool: "similar_incidents", service: null, summary: "[verified_incident] ..." }],
  timeline: [{ t: 100, msg: "anomaly confirmed on ['web']" }, { t: 107, msg: "diagnosed down on web" },
    { t: 107, msg: "policy: execute - autopilot: low-risk runbook allowed by the rulebook" },
    { t: 115, msg: "executed restart_service on web by autopilot" }, { t: 151, msg: "verification: recovered (100% of 19 checkouts)" }],
  report: { summary: "web shows signs of down." }, report_meta: { provider: "template", llm_pending: false },
};
const telegramApproved = {
  id: "dfafd0c5", opened_t: 200, status: "recovered", services: ["payments"], likely_cause: "bad_deploy",
  actions: [{ t: 207, runbook_id: "rollback_release", service: "payments", verdict: "needs_approval", risk: "high",
    executed: true, approved_by: "telegram:7769231832", executed_t: 252 }],
  verification: { outcome: "recovered", t: 276 },
  timeline: [{ t: 207, msg: "diagnosed bad_deploy on payments" }, { t: 252, msg: "executed rollback_release on payments by human:telegram:7769231832" }],
};

describe("approver channel parsing", () => {
  it("maps the API's approver strings to channels", () => {
    expect(approverChannel("human:telegram:7769231832")).toMatchObject({ channel: "Telegram", id: "7769231832" });
    expect(approverChannel("telegram:7769231832").channel).toBe("Telegram");
    expect(approverChannel("human:dashboard").channel).toBe("Dashboard");
    expect(approverChannel("dashboard").channel).toBe("Dashboard");
    expect(approverChannel("autopilot").channel).toBe("Autopilot");
    expect(approverChannel("benchmark-operator").channel).toBe("Script");
    expect(approverChannel(null).channel).toBe("Not reported");
    expect(approverChannel(undefined).channel).toBe("Not reported");
  });
});

describe("pipeline stage derivation", () => {
  it("autopilot: approval skipped, all other stages done with elapsed seconds", () => {
    const s = deriveStages(autopilotRecovered);
    expect(s.map((x) => x.status)).toEqual(["done", "done", "done", "skipped", "done", "done"]);
    expect(s[4]).toMatchObject({ elapsed: 15, detail: "restart_service" });
    expect(s[5]).toMatchObject({ elapsed: 51, detail: "recovered" });
  });
  it("needs approval and waiting: the approval stage is current", () => {
    const waiting = { ...telegramApproved, status: "awaiting_approval", verification: null,
      actions: [{ ...telegramApproved.actions[0], executed: false, approved_by: null, executed_t: undefined }] };
    const s = deriveStages(waiting);
    expect(s[3]).toMatchObject({ status: "current", detail: "waiting for a person" });
    expect(s[4].status).toBe("pending");
  });
  it("approved on Telegram: approval done with the approver", () => {
    const s = deriveStages(telegramApproved);
    expect(s[3]).toMatchObject({ status: "done", detail: "telegram:7769231832" });
    expect(s[5].status).toBe("done");
  });
  it("blocked by the kill switch: fix skipped, nothing invented", () => {
    const blocked = { id: "x", opened_t: 1, status: "escalated", likely_cause: "disk_fill",
      actions: [{ t: 2, verdict: "blocked", reason: "kill switch is on: nothing is executed", executed: false }] };
    const s = deriveStages(blocked);
    expect(s[4]).toMatchObject({ status: "skipped", detail: "blocked by policy" });
    expect(s[5].status).toBe("pending");
  });
  it("missing fields leave stages pending, never done", () => {
    const s = deriveStages({ id: "y", status: "open" });
    expect(s[0].status).toBe("done");
    expect(s.slice(1).every((x) => x.status === "current" || x.status === "pending")).toBe(true);
    expect(s[1].status).toBe("current");
  });
  it("follows the newest active incident and the recently closed one", () => {
    const list = [autopilotRecovered, { ...telegramApproved, status: "verifying" }];
    expect(newestActive(list)?.id).toBe("dfafd0c5");
    expect(recentClosed([autopilotRecovered], 200)?.id).toBe("d38555ed");
    expect(recentClosed([autopilotRecovered], 5000)).toBeUndefined();
  });
});

describe("report provenance", () => {
  it("never relabels a template report as LLM", () => {
    expect(reportProvenance({ provider: "template" })).toMatchObject({ provider: "template", validated: undefined });
    expect(reportProvenance({ provider: "template", fallback_reasons: ["gemini: ReadTimeout"] }).fallbackReasons).toEqual(["gemini: ReadTimeout"]);
    expect(reportProvenance({ provider: "gemini", llm_disagreed: true })).toMatchObject({ provider: "gemini", validated: true, disagreed: true });
    expect(reportProvenance(undefined).provider).toBeUndefined();
  });
});

describe("investigation trace", () => {
  it("is built from evidence, ranking, policy, approval, action and verification", () => {
    const t = buildTrace(autopilotRecovered);
    expect(t.map((x) => x.kind)).toEqual(["evidence", "evidence", "evidence", "causes", "policy", "approval", "action", "verification"]);
    expect(t[0]).toMatchObject({ source: "Prometheus metrics", id: "ev1" });
    expect(t[1].source).toBe("Docker container");
    expect(t[2].source).toBe("Knowledge base");
    expect(t[3].summary).toContain("margin 0.97");
    expect(t[5].summary).toBe("not needed (policy allowed it)");
    expect(t[6].summary).toBe("restart_service on web · executed");
    expect(t[7].summary).toContain("recovered");
  });
  it("shows the Telegram channel for an approved action", () => {
    const t = buildTrace(telegramApproved);
    expect(t.find((x) => x.kind === "approval")).toMatchObject({ channel: "Telegram" });
  });
  it("says abstained and Not reported instead of inventing", () => {
    const t = buildTrace({ id: "z", abstained: true, likely_cause: "insufficient_evidence" });
    expect(t.find((x) => x.kind === "causes")?.summary).toContain("abstained: insufficient evidence");
    expect(t.find((x) => x.kind === "policy")?.summary).toBe("Not reported");
    expect(t.find((x) => x.kind === "verification")?.summary).toBe("Not reported");
    expect(evidenceSource("unknown_tool")).toBe("Other");
  });
  it("counts outcomes over returned incidents only", () => {
    const blocked = { status: "escalated", actions: [{ verdict: "blocked", reason: "kill switch is on: nothing is executed" }] };
    const abst = { status: "escalated", abstained: true };
    const waiting = { status: "awaiting_approval" };
    expect(outcomeCounts([autopilotRecovered, blocked, abst, waiting])).toEqual({
      total: 4, fixedVerified: 1, waitingApproval: 1, blockedKillSwitch: 1, abstained: 1 });
  });
});

describe("chart mappings", () => {
  it("keeps failed polls as gaps", () => {
    const { rows, names } = scoreSeries({ web: [{ at: 1, value: 0.3 }, { at: 2, value: null }] });
    expect(names).toEqual(["web"]);
    expect(rows).toEqual([{ at: 1, web: 0.3 }, { at: 2, web: null }]);
  });
  it("computes durations from incident timestamps only", () => {
    expect(incidentDurations([autopilotRecovered])).toEqual([{ id: "d38555ed", diagnose_s: 7, verified_s: 51, outcome: "recovered" }]);
    expect(incidentDurations([{ id: "n", opened_t: 1 }])).toEqual([{ id: "n", diagnose_s: null, verified_s: null, outcome: null }]);
  });
  it("counts executed actions by runbook and by channel, ignoring verification rows", () => {
    const audit = [
      { t: 60, runbook: "restart_service", service: "web", actor: "autopilot", ok: true },
      { t: 70, runbook: "rollback_release", service: "payments", actor: "human:telegram:7769231832", ok: true },
      { t: 80, kind: "verification", runbook: "restart_service", service: "web", outcome: "recovered" },
    ];
    expect(actionsByRunbook(audit)).toEqual({ data: [{ minute: 60, restart_service: 1, rollback_release: 1 }], runbooks: ["restart_service", "rollback_release"] });
    expect(actionsByChannel(audit)).toMatchObject({ Autopilot: 1, Telegram: 1, Dashboard: 0 });
  });
});
