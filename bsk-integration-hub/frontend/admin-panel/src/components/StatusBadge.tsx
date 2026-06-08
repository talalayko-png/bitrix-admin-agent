const COLORS: Record<string, string> = {
  succeeded: 'green',
  queued: 'blue',
  running: 'blue',
  pending: 'slate',
  awaiting_approval: 'amber',
  failed: 'red',
  dead: 'red',
  cancelled: 'slate',
}

export function StatusBadge({ status }: { status: string }) {
  const color = COLORS[status] || 'slate'
  return <span className={`badge ${color}`}>{status}</span>
}
