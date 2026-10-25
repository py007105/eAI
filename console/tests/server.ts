import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";
export const server = setupServer(
  http.get("http://localhost/api/scorecard", () => HttpResponse.json({ runs: 0, by_scenario: {} })),
  http.get("http://localhost/api/status", () =>
    HttpResponse.json({
      mode: "watch-only",
      kill_switch: false,
      calibration: { show_probability: false },
      protected_services: ["payments"],
      policy: { summary: "Read-only test policy" },
      open_incidents: 0,
    }),
  ),
  http.get("http://localhost/api/services", () =>
    HttpResponse.json({
      services: {
        payments: { score: 0, anomalous: false, state: { running: true } },
        inventory: {},
      },
      topology: { web: ["payments", "inventory"] },
      depfail: {},
    }),
  ),
  http.get("http://localhost/api/incidents", () => HttpResponse.json([])),
  http.get("http://localhost/api/approvals", () => HttpResponse.json([])),
  http.get("http://localhost/api/audit", () => HttpResponse.json([])),
);
