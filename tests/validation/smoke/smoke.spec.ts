// @ts-check
const { test, expect } = require('@playwright/test');

const ACCOUNTING_ROUTES = [
  { path: '/', label: 'Dashboard' },
  { path: '/accounting/events', label: 'Events' },
  { path: '/accounting/decisions', label: 'Decisions' },
  { path: '/accounting/replay', label: 'Replay' },
  { path: '/ledger/entries', label: 'Ledger Entries' },
  { path: '/ledger/accounts', label: 'Chart of Accounts' },
  { path: '/ledger/periods', label: 'Periods' },
  { path: '/tax/registers', label: 'Tax Registers' },
  { path: '/tax/assignments', label: 'Tax Assignments' },
  { path: '/tax/policies', label: 'Tax Policies' },
  { path: '/reports/drafts', label: 'Report Drafts' },
  { path: '/reports/templates', label: 'Report Templates' },
  { path: '/reports/audit', label: 'Report Audit' },
  { path: '/reconciliation/runs', label: 'Recon Runs' },
  { path: '/reconciliation/matches', label: 'Recon Matches' },
  { path: '/reconciliation/gaps', label: 'Recon Gaps' },
  { path: '/control/actions', label: 'Control Actions' },
  { path: '/control/approval', label: 'Approval Queue' },
  { path: '/control/state', label: 'System State' },
  { path: '/control/metrics', label: 'Metrics' },
];

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';

for (const route of ACCOUNTING_ROUTES) {
  test(`${route.label} — load + render`, async ({ page }) => {
    const start = Date.now();
    const resp = await page.goto(BASE_URL + route.path, { waitUntil: 'networkidle' });
    const duration = Date.now() - start;

    expect(resp?.status()).toBe(200);
    expect(await page.locator('h1').count()).toBeGreaterThanOrEqual(1);
    expect(await page.locator('table, .grid, .space-y-1, .bg-white').count()).toBeGreaterThanOrEqual(1);

    console.log(`[${route.label}] ${duration}ms OK`);
  });

  test(`${route.label} — reload persistence`, async ({ page }) => {
    await page.goto(BASE_URL + route.path, { waitUntil: 'networkidle' });
    const title1 = await page.locator('h1').textContent();
    await page.reload({ waitUntil: 'networkidle' });
    const title2 = await page.locator('h1').textContent();
    expect(title1).toBe(title2);
  });

  test(`${route.label} — back navigation`, async ({ page }) => {
    await page.goto(BASE_URL + route.path, { waitUntil: 'networkidle' });
    await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
    await page.goBack({ waitUntil: 'networkidle' });
    const title = await page.locator('h1').textContent();
    expect(title?.length).toBeGreaterThan(0);
  });
}
