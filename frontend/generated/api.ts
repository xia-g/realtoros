/** Auto-generated API client for Realtor OS **/
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const endpoints = {
  // Platform
  platform: {
    settings: '/api/v1/platform/settings',
    domains: '/api/v1/platform/domains',
  },
  // Auth
  auth: {
    login: '/api/v1/auth/login',
    logout: '/api/v1/auth/logout',
    me: '/api/v1/auth/me',
  },
  // Clients
  clients: {
    list: '/api/v1/clients',
    detail: (id: string) => `/api/v1/clients/${id}`,
  },
  // Properties
  properties: {
    list: '/api/v1/properties',
    detail: (id: string) => `/api/v1/properties/${id}`,
  },
  // Deals
  deals: {
    list: '/api/v1/deals',
    detail: (id: string) => `/api/v1/deals/${id}`,
  },
  // Documents
  documents: {
    list: '/api/v1/documents',
    detail: (id: string) => `/api/v1/documents/${id}`,
  },
  // Compliance
  compliance: {
    audits: '/api/v1/compliance/audits',
    checkpoints: '/api/v1/compliance/checkpoints',
  },
  // Knowledge
  knowledge: {
    search: '/api/v1/knowledge/search',
    graph: '/api/v1/knowledge/graph',
  },
  // AI
  ai: {
    copilot: '/api/v1/ai/copilot',
    sessions: '/api/v1/ai/sessions',
    calls: '/api/v1/ai/calls',
  },
  // Operations
  operations: {
    slas: '/api/v1/operations/slas',
    actions: '/api/v1/operations/actions',
    escalations: '/api/v1/operations/escalations',
  },
  // Analytics
  analytics: {
    dashboard: '/api/v1/analytics/dashboard',
    funnel: '/api/v1/analytics/funnel',
    portfolio: '/api/v1/analytics/portfolio',
  },
  // Executive
  executive: {
    dashboard: '/api/v1/executive/dashboard',
    recommendations: '/api/v1/executive/recommendations',
  },
  // Admin
  admin: {
    settings: '/api/v1/admin/settings',
    health: '/api/v1/admin/health',
  },
} as const

export interface ApiResponse<T> {
  data: T
  status: number
  message?: string
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem('token')

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Unknown error' }))
    throw new Error(error.message || `API Error: ${response.status}`)
  }

  return response.json()
}

// Typed endpoints
export const api = {
  platform: {
    getSettings: () => apiRequest(endpoints.platform.settings),
    updateSettings: (data: any) =>
      apiRequest(endpoints.platform.settings, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    getDomains: () => apiRequest(endpoints.platform.domains),
  },
  auth: {
    login: (credentials: { email: string; password: string }) =>
      apiRequest(endpoints.auth.login, {
        method: 'POST',
        body: JSON.stringify(credentials),
      }),
    logout: () => apiRequest(endpoints.auth.logout, { method: 'POST' }),
    getMe: () => apiRequest(endpoints.auth.me),
  },
  clients: {
    list: () => apiRequest(endpoints.clients.list),
    get: (id: string) => apiRequest(endpoints.clients.detail(id)),
    create: (data: any) =>
      apiRequest(endpoints.clients.list, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },
  properties: {
    list: () => apiRequest(endpoints.properties.list),
    get: (id: string) => apiRequest(endpoints.properties.detail(id)),
  },
  deals: {
    list: () => apiRequest(endpoints.deals.list),
    get: (id: string) => apiRequest(endpoints.deals.detail(id)),
    create: (data: any) =>
      apiRequest(endpoints.deals.list, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },
  documents: {
    list: () => apiRequest(endpoints.documents.list),
    get: (id: string) => apiRequest(endpoints.documents.detail(id)),
  },
  compliance: {
    audits: () => apiRequest(endpoints.compliance.audits),
    checkpoints: () => apiRequest(endpoints.compliance.checkpoints),
  },
  knowledge: {
    search: (query: string) =>
      apiRequest(endpoints.knowledge.search, {
        body: JSON.stringify({ query }),
      }),
    graph: () => apiRequest(endpoints.knowledge.graph),
  },
  ai: {
    copilot: (message: string) =>
      apiRequest(endpoints.ai.copilot, {
        method: 'POST',
        body: JSON.stringify({ message }),
      }),
  },
} as const

export default api
