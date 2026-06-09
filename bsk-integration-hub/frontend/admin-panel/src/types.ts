export interface Flags {
  app_env: string
  dry_run: boolean
  use_mock_connectors: boolean
  allow_real_api: boolean
  real_reads_enabled: boolean
  real_writes_enabled: boolean
  real_api_enabled: boolean
  queue_backend: string
  approval_required_for: string[]
}

export interface Operation {
  id: number
  idempotency_key: string
  type: string
  source: string
  workflow_key: string | null
  status: string
  payload: Record<string, unknown>
  result: Record<string, unknown> | null
  error: string | null
  attempts: number
  max_attempts: number
  requires_approval: boolean
  approved_by: string | null
  approved_at: string | null
  dry_run: boolean
  scheduled_at: string | null
  created_at: string
  updated_at: string
}

export interface Log {
  id: number
  level: string
  message: string
  data: Record<string, unknown> | null
  created_at: string
}

export interface Snapshot {
  id: number
  entity_ref: string
  action: string
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  created_at: string
}

export interface OperationDetail {
  operation: Operation
  logs: Log[]
  snapshots: Snapshot[]
}

export interface Mapping {
  id: number
  b24_type: string
  b24_id: string
  ms_type: string
  ms_id: string
  meta: Record<string, unknown> | null
  created_at: string
}

export interface Workflow {
  key: string
  name: string
  type: string
  trigger_source: string
  enabled: boolean
  config: Record<string, unknown>
  dry_run_override: boolean | null
}

export interface Dashboard {
  counts: Record<string, number>
  flags: Flags
  queue_depth: number | null
  recent: Operation[]
}

export interface Plan {
  action: string
  entity_ref: string
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  summary: string
}

export interface AssistantAnswer {
  enabled: boolean
  question: string
  answer: string
}
