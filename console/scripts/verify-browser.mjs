import { chromium } from "@playwright/test";
import { spawn, execFileSync } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

// Real observations only: no response interception or fixture payloads.
const folder = path.resolve(
  "evidence",
  new Date().toISOString().replace(/[:.]/g, "-"),
);
await mkdir(folder, { recursive: true });
const report = {
  timestamp: new Date().toISOString(),
  candidate: execFileSync("git", ["rev-parse", "HEAD"], {
    encoding: "utf8",
  }).trim(),
  workingTree: execFileSync("git", ["status", "--short", "--", "console"], {
    encoding: "utf8",
  }).trim(),
  backendRef: null,
  pages: [],
  proxies: [],
  polling: [],
  failures: [],
};
const routes = [
  "/",
  "/console",
  "/console/incidents",
  "/console/topology",
  "/console/approvals",
  "/console/safety",
  "/console/audit",
  "/console/results",
  "/console/incidents/unavailable-record",
];
const sizes = [
  { width: 1440, height: 900 },
  { width: 1280, height: 720 },
  { width: 390, height: 844 },
];
report.backend = await fetch("http://127.0.0.1:8000/health", {
  signal: AbortSignal.timeout(3000),
})
  .then((r) => ({ status: r.status }))
  .catch(() => ({ unreachable: true }));
const browser = await chromium.launch({
  headless: true,
  executablePath:
    process.env.CONSOLE_BROWSER_PATH ||
    "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe",
});
try {
  for (const mode of ["dev", "preview"]) {
    const port = mode === "dev" ? 4173 : 4180;
    const server = spawn(
      process.execPath,
      [
        "node_modules/vite/bin/vite.js",
        ...(mode === "preview" ? ["preview"] : []),
        "--host",
        "127.0.0.1",
        "--port",
        String(port),
        "--strictPort",
      ],
      { stdio: "ignore" },
    );
    try {
      const base = `http://127.0.0.1:${port}`;
      let ready = false;
      for (let i = 0; i < 30; i++) {
        ready = await fetch(base)
          .then((r) => r.ok)
          .catch(() => false);
        if (ready) break;
        await new Promise((r) => setTimeout(r, 250));
      }
      if (!ready) throw new Error(`${mode} did not start`);
      for (const endpoint of [
        "health",
        "status",
        "services",
        "incidents",
        "approvals",
        "audit",
      ]) {
        const outcome = await fetch(`${base}/api/${endpoint}`, {
          signal: AbortSignal.timeout(6000),
        })
          .then((r) => ({
            status: r.status,
            contentType: r.headers.get("content-type"),
          }))
          .catch(() => ({ unreachable: true }));
        report.proxies.push({ mode, endpoint, ...outcome });
      }
      for (const size of sizes) {
        const context = await browser.newContext({
          viewport: size,
          reducedMotion: "reduce",
        });
        const page = await context.newPage();
        const statusRequests = [];
        page.on("request", (r) => {
          if (
            new URL(r.url()).pathname.startsWith("/api/") &&
            r.method() !== "GET"
          )
            report.failures.push("Non-GET API request");
          if (new URL(r.url()).pathname === "/api/status")
            statusRequests.push(Date.now());
        });
        for (const route of routes) {
          await page.goto(base + route);
          await page.getByRole("heading", { level: 1 }).waitFor();
          if (route !== "/") await page.getByRole("status").waitFor();
          if (route !== "/" && report.backend.unreachable)
            await page
              .getByRole("status")
              .filter({ hasText: "Disconnected" })
              .waitFor();
          await page.waitForTimeout(250);
          if (route === "/console" && size.width === 1440) {
            const start = statusRequests.length;
            await page.waitForTimeout(4300);
            const observed = statusRequests.slice(start);
            report.polling.push({
              mode,
              observedAt: observed,
              requests: observed.length,
            });
            if (observed.length < 2)
              report.failures.push(`${mode} polling did not retry twice`);
          }
          const dimensions = await page.evaluate(() => ({
            width: innerWidth,
            scroll: document.documentElement.scrollWidth,
          }));
          const connection =
            route === "/" ? null : await page.getByRole("status").textContent();
          const heading = await page
            .getByRole("heading", { level: 1 })
            .textContent();
          report.pages.push({
            mode,
            route,
            ...size,
            heading,
            connection,
            overflow: dimensions.scroll > dimensions.width,
          });
          if (dimensions.scroll > dimensions.width)
            report.failures.push(`${mode} ${route} overflow at ${size.width}`);
          if (
            mode === "preview" &&
            ["/", "/console", "/console/topology"].includes(route)
          )
            await page.screenshot({
              path: path.join(
                folder,
                `${route === "/" ? "landing" : route.split("/").at(-1)}-${size.width}.png`,
              ),
              fullPage: true,
            });
          if (route === "/console" && size.width === 390) {
            await page.getByRole("button", { name: "Open navigation" }).click();
            await page
              .getByRole("link", { name: "Incidents", exact: true })
              .click();
            await page
              .getByRole("heading", { name: "Incidents", exact: true })
              .waitFor();
          }
        }
        await context.close();
      }
    } finally {
      server.kill();
    }
  }
} finally {
  await browser.close();
  await writeFile(
    path.join(folder, "report.json"),
    JSON.stringify(report, null, 2),
  );
}
console.log(
  JSON.stringify(
    {
      folder,
      pages: report.pages.length,
      failures: report.failures,
      backend: report.backend,
    },
    null,
    2,
  ),
);
if (report.failures.length) process.exitCode = 1;
