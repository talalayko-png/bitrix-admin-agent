import type {
  AssistantAnswer,
  Dashboard,
  Mapping,
  Operation,
  OperationDetail,
  Plan,
  Workflow,
} from './types'

const BASE = (import.meta.env.VITE_API_BASE as string) ?? ''
const TOKEN_KEY = 'bsk_admin_token'

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || (import.meta.env.VITE_ADMIN_TOKEN as string) || ''
}
export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message)
  }
}

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(BASE + path, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`,
      ...(opts.headers || {}),
    },
  })
  if (res.status === 204) return undefined as T
  const text = await res.text()
  const data = text ? JSON.parse(text) : null
  if (!res.ok) {
    const detail =
      (data && typeof data === 'object' && 'detail' in data && (data as any).detail) ||
      res.statusText
    throw new ApiError(res.status, String(detail), data)
  }
  return data as T
}

export const api = {
  dashboard: () => req<Dashboard>('/api/admin/dashboard'),
  settings: () => req<Record<string, unknown>>('/api/admin/settings'),

  operations: (status?: string) =>
    req<Operation[]>(`/api/admin/operations${status ? `?status=${encodeURIComponent(status)}` : ''}`),
  operation: (id: number) => req<OperationDetail>(`/api/admin/operations/${id}`),
  retry: (id: number) => req<{ ok: boolean }>(`/api/admin/operations/${id}/retry`, { method: 'POST' }),
  approve: (id: number, approved_by?: string) =>
    req<{ ok: boolean }>(`/api/admin/operations/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved_by }),
    }),
  cancel: (id: number) => req<{ ok: boolean }>(`/api/admin/operations/${id}/cancel`, { method: 'POST' }),
  dryRun: (id: number) => req<Plan>(`/api/admin/operations/${id}/dry-run`, { method: 'POST' }),

  mappings: () => req<Mapping[]>('/api/admin/mappings'),
  createMapping: (m: Omit<Mapping, 'id' | 'created_at'>) =>
    req<Mapping>('/api/admin/mappings', { method: 'POST', body: JSON.stringify(m) }),
  deleteMapping: (id: number) => req<void>(`/api/admin/mappings/${id}`, { method: 'DELETE' }),

  workflows: () => req<Workflow[]>('/api/admin/workflows'),
  updateWorkflow: (key: string, body: Partial<Pick<Workflow, 'enabled' | 'config' | 'dry_run_override'>>) =>
    req<Workflow>(`/api/admin/workflows/${key}`, { method: 'PUT', body: JSON.stringify(body) }),

  assistant: (question: string) =>
    req<AssistantAnswer>('/api/admin/assistant/query', {
      method: 'POST',
      body: JSON.stringify({ question }),
    }),

  simulateDeal: (deal_id: string, stage: string) =>
    req<{ event_id: number; operation_ids: number[] }>('/api/admin/simulate/deal', {
      method: 'POST',
      body: JSON.stringify({ deal_id, stage }),
    }),
}
