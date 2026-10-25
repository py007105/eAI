// Synthetic browser regression ONLY. Fixtures and captures never represent a live backend.
import { chromium, expect } from '@playwright/test';
import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
const output = 'tests/evidence/presentation';
await mkdir(output, { recursive: true });
const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', '4190', '--strictPort'], { stdio: 'ignore' });
const browser = await chromium.launch({ headless: true });
const report = { kind: 'synthetic test fixtures, not live integration', failures: [], views: [] };
const incident = {
  id: 'test-incident', opened_t: 100, closed_t: 142, status: 'recovered', services: ['web'], likely_cause: 'down',
  ranking: [{ service: 'web', score: 0.98 }],
  actions: [{ t: 107, runbook_id: 'restart_service', service: 'web', verdict: 'execute', risk: 'low', reason: 'Low-risk action allowed by policy', executed: true, executed_t: 113 }],
  verification: { outcome: 'recovered', t: 142, probes: 19, success_rate: 1 },
  before: { checkout_success: 0, error_ratio: .3, p95_s: 1.2 }, after: { checkout_success: 1, error_ratio: 0, p95_s: .12 },
  evidence: Array.from({ length: 6 }, (_, i) => ({ id: `ev${i}`, tool: 'metrics', summary: `Test evidence ${i}` })),
  report: { summary: 'Fixture: web stopped responding. The approved runbook restarted the service and checkout probes passed.' }, report_meta: { provider: 'template' },
};
try {
  for (let i = 0; i < 40; i++) { if (await fetch('http://127.0.0.1:4190').then(r => r.ok).catch(() => false)) break; await new Promise(r => setTimeout(r, 250)); }
  for (const size of [{ width: 1440, height: 900 }, { width: 1280, height: 720 }, { width: 390, height: 844 }]) {
    const context = await browser.newContext({ viewport: size, reducedMotion: 'reduce' });
    const page = await context.newPage();
    page.on('pageerror', e => report.failures.push(e.message));
    let outage = false, finished = false;
    await page.route('**/api/**', async route => {
      const req = route.request();
      if (req.method() !== 'GET') report.failures.push(`Non-GET ${req.url()}`);
      const path = new URL(req.url()).pathname;
      if (outage && path === '/api/incidents') return route.fulfill({ status: 503, body: '' });
      const payloads = {
        '/api/status': { mode: 'autopilot', kill_switch: false, open_incidents: 0, calibration: { show_probability: false }, policy: { runbook_risk: { restart_service: 'low', rollback_release: 'high' } } },
        '/api/services': { services: Object.fromEntries(['web','orders','payments','inventory'].map(n => [n, { anomalous: false, score: .02, state: { running: true } }])), topology: { web: ['orders','inventory'], orders: ['payments','inventory'] } },
        '/api/incidents': [incident], '/api/approvals': [], '/api/audit': [], '/api/scorecard': { runs: 0, by_scenario: {} },
        '/api/challenge/test-run/status': { run_id: 'test-run', state: finished ? 'finished' : 'running', elapsed_s: 50 },
        '/api/challenge/test-run/reveal': { truth: { run_id: 'test-run', scenario: 'crash', target: 'web' }, score: { detected: true, recovered: true, time_to_detect_s: 6, time_to_verified_recovery_s: 42, failed_request_pct: 10, false_alerts: 0, harmful_interventions: 0 } },
      };
      return route.fulfill({ json: payloads[path] ?? { detail: 'Not found' }, status: payloads[path] ? 200 : 404 });
    });
    for (const route of ['/', '/console', '/console/live', '/console/topology', '/console/integrations']) {
      await page.goto(`http://127.0.0.1:4190${route}`);
      if (route !== '/') await expect(page.locator('.connection')).toContainText('Live');
      if (route === '/console/live') {
        await page.getByLabel('Choose incident').selectOption('test-incident');
        await page.getByRole('button', { name: 'Inspect Fix executed' }).click();
        await expect(page.getByText('Fix executed · done')).toBeVisible();
        await page.locator('summary').filter({ hasText: 'Evidence' }).click();
        await expect(page.getByText('Test evidence 5')).toBeVisible();
        await expect(page.getByText('120 ms')).toBeVisible();
        await page.getByRole('button', { name: 'Focus view' }).click();
        await expect(page.locator('.sidebar')).toBeHidden();
        await page.keyboard.press('Escape');
        await expect(page.getByRole('button', { name: 'Focus view' })).toBeVisible();
        await page.getByLabel('Evaluator run ID').fill('test-run');
        await page.getByRole('button', { name: 'Check run' }).click();
        await expect(page.getByText(/ground truth remains hidden/)).toBeVisible();
        await expect(page.getByRole('button', { name: 'Reveal result' })).toHaveCount(0);
        finished = true;
        await page.getByRole('button', { name: 'Check run' }).click();
        await page.getByRole('button', { name: 'Reveal result' }).click();
        await expect(page.getByRole('heading', { name: 'crash · web' })).toBeVisible();
        outage = true;
        await expect(page.getByText('Live incident view unavailable')).toBeVisible({ timeout: 7000 });
        await expect(page.getByText('Fix executed · done')).toHaveCount(0);
        outage = false;
        await expect(page.getByText('Fixture: web stopped responding.', { exact: false })).toBeVisible({ timeout: 7000 });
      }
      if (route === '/console/topology') {
        await page.getByRole('button', { name: 'Select service web' }).click();
        await expect(page.locator('.topology-detail h2')).toHaveText('web');
        if (size.width === 1440) {
          await page.getByRole('button', { name: '3D', exact: true }).click();
          await expect(page.locator('canvas')).toBeVisible({ timeout: 15000 });
          await page.getByRole('button', { name: 'payments', exact: true }).click();
          await expect(page.locator('.topology-detail h2')).toHaveText('payments');
          await page.getByRole('button', { name: '2D', exact: true }).click();
        }
      }
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
      if (overflow) report.failures.push(`${route}: overflow at ${size.width}`);
      report.views.push({ route, ...size, overflow });
      await page.screenshot({ path: `${output}/${route === '/' ? 'landing' : route.split('/').at(-1)}-${size.width}.png`, fullPage: true });
    }
    if (size.width === 390) {
      await page.getByRole('button', { name: 'Open navigation' }).click();
      await page.getByRole('button', { name: 'Dismiss navigation' }).click({ position: { x: 350, y: 500 } });
      await expect(page.getByRole('navigation', { name: 'Console navigation' })).toBeHidden();
    }
    await context.close();
  }
} catch (e) { report.failures.push(e.message); }
finally { await browser.close(); server.kill(); await writeFile(`${output}/report.json`, JSON.stringify(report, null, 2)); }
console.log(JSON.stringify(report, null, 2));
if (report.failures.length) process.exitCode = 1;
