const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.spcnn.ru'

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== 'undefined'
    ? JSON.parse(localStorage.getItem('realtor-auth') || '{}')?.state?.token
    : null

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options?.headers,
  }

  const res = await fetch(`${API_URL}${path}`, { ...options, headers })

  if (!res.ok) {
    const body = await res.text()
    throw new ApiError(res.status, body || res.statusText)
  }

  return res.json()
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}

// ── API endpoints ──
export const endpoints = {
  // Auth
  login: '/api/v1/auth/login',
  logout: '/api/v1/auth/logout',
  session: '/api/v1/auth/session',

  // Clients
  clients: '/api/v1/clients',
  client: (id: string) => `/api/v1/clients/${id}`,
  clientDeals: (id: string) => `/api/v1/clients/${id}/deals`,
  clientDocuments: (id: string) => `/api/v1/clients/${id}/documents`,

  // Leads
  leads: '/api/v1/leads',
  lead: (id: string) => `/api/v1/leads/${id}`,
  leadConvert: (id: string) => `/api/v1/leads/${id}/convert`,
  leadQualify: (id: string) => `/api/v1/leads/${id}/qualify`,

  // Properties
  properties: '/api/v1/properties',
  property: (id: string) => `/api/v1/properties/${id}`,

  // Deals
  deals: '/api/v1/deals',
  deal: (id: string) => `/api/v1/deals/${id}`,
  dealCompliance: (id: string) => `/api/v1/deals/${id}/compliance`,
  dealRisks: (id: string) => `/api/v1/deals/${id}/risks`,
  dealTimeline: (id: string) => `/api/v1/deals/${id}/timeline`,
  dealHealth: (id: string) => `/api/v1/deals/${id}/health`,

  // Documents
  documents: '/api/v1/documents',
  document: (id: string) => `/api/v1/documents/${id}`,
  documentValidate: (id: string) => `/api/v1/documents/${id}/validate`,

  // Compliance
  compliance: '/api/v1/compliance',
  complianceDeal: (id: string) => `/api/v1/compliance/deals/${id}`,

  // Operations
  operationsSla: '/api/v1/sla',
  operationsActions: '/api/v1/actions',
  operationsEscalations: '/api/v1/escalations',

  // AI
  aiAsk: '/api/v1/ai/ask',
  aiSessions: '/api/v1/ai/sessions',

  // Knowledge
  knowledgeSearch: '/api/v1/knowledge/search',
  knowledgeGraph: '/api/v1/knowledge/graph',

  // Platform
  platformSettings: '/api/v1/platform/settings',
  platformDomains: '/api/v1/platform/domains',
  platformHealth: '/api/v1/platform/health',

  // ── Accounting ──
  accountingEvents: '/api/v1/accounting/events',
  accountingEvent: (id: string) => `/api/v1/accounting/events/${id}`,
  accountingDecision: (id: string) => `/api/v1/accounting/events/${id}/decision`,
  accountingReplay: '/api/v1/accounting/replay',

  // ── Ledger ──
  ledgerEntries: '/api/v1/ledger/entries',
  ledgerEntry: (id: string) => `/api/v1/ledger/entries/${id}`,
  ledgerAccounts: '/api/v1/ledger/accounts',
  ledgerPost: '/api/v1/ledger/post',
  ledgerReverse: '/api/v1/ledger/reverse',
  ledgerPeriodClose: (id: string) => `/api/v1/ledger/period/${id}/close`,
  ledgerPeriodOpen: (id: string) => `/api/v1/ledger/period/${id}/open`,

  // ── Tax ──
  taxRegisters: '/api/v1/tax/registers',
  taxRegister: (id: string) => `/api/v1/tax/registers/${id}`,
  taxAssignments: '/api/v1/tax/assignments',
  taxPolicies: '/api/v1/tax/policies',
  taxRecalculate: '/api/v1/tax/recalculate',
  taxPeriodClose: '/api/v1/tax/period/close',
  taxExplanations: '/api/v1/tax/explanations',
  taxSeed: '/api/v1/tax/seed',
  taxMetrics: '/api/v1/tax/metrics',
  taxPeriods: '/api/v1/tax/periods',

  // ── Reports ──
  reports: '/api/v1/reports',
  report: (id: string) => `/api/v1/reports/${id}`,
  reportGenerate: '/api/v1/reports/generate',
  reportValidate: (id: string) => `/api/v1/reports/${id}/validate`,
  reportAudit: (id: string) => `/api/v1/reports/${id}/audit`,
  reportApprove: (id: string) => `/api/v1/reports/${id}/approve`,
  reportSubmit: (id: string) => `/api/v1/reports/${id}/submit`,
  reportAuditLog: (id: string) => `/api/v1/reports/${id}/audit-log`,
  reportHash: (id: string) => `/api/v1/reports/${id}/hash`,
  reportReadySubmit: (id: string) => `/api/v1/reports/${id}/ready-to-submit`,
  reportTemplates: '/api/v1/reports/templates',
  reportTemplatesSeed: '/api/v1/reports/templates/seed',

  // ── Reconciliation ──
  reconciliationRun: '/api/v1/reconciliation/run',
  reconciliationRuns: '/api/v1/reconciliation/runs',
  reconciliationRunDetail: (id: string) => `/api/v1/reconciliation/runs/${id}`,
  reconciliationMatches: (id: string) => `/api/v1/reconciliation/runs/${id}/matches`,
  reconciliationGaps: (id: string) => `/api/v1/reconciliation/runs/${id}/gaps`,
  reconciliationItems: (id: string) => `/api/v1/reconciliation/runs/${id}/items`,
  reconciliationExplanations: (id: string) => `/api/v1/reconciliation/runs/${id}/explanations`,
  reconciliationClose: (id: string) => `/api/v1/reconciliation/runs/${id}/close`,

  // ── Control Plane ──
  controlState: '/api/v1/control/state',
  controlActions: '/api/v1/control/actions',
  controlAction: (id: string) => `/api/v1/control/actions/${id}`,
  controlExecute: '/api/v1/control/actions/execute',
  controlApprove: (id: string) => `/api/v1/control/actions/${id}/approve`,
  controlMetricsRecord: '/api/v1/control/metrics',
  controlMetrics: '/api/v1/control/metrics',

  // ── Companies ──
  companies: '/api/v1/companies',
  company: (id: string) => `/api/v1/companies/${id}`,

  // ── Uploads ──
  uploadDocument: '/api/v1/upload/document',
  uploadBank: '/api/v1/upload/bank',

  // ── Obligations ──
  obligations: '/api/v1/obligations',
  obligation: (id: string) => `/api/v1/obligations/${id}`,
  obligationOverdue: '/api/v1/obligations/overdue',
  obligationTypes: '/api/v1/obligations/types',
}
