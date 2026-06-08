import { useEffect, useState } from 'react'
import { api } from '../api'
import { JsonView } from '../components/JsonView'
import { StatusBadge } from '../components/StatusBadge'
import type { OperationDetail, Operation, Plan } from '../types'
import { fmt } from '../util'

const STATUSES = [
  '',
  'pending',
  'queued',
  'running',
  'awaiting_approval',
  'succeeded',
  'failed',
  'cancelled',
  'dead',
]

export default function Operations({
  initialSelected,
  onSelect,
}: {
  initialSelected: number | null
  onSelect: (id: number | null) => void
}) {
  const [ops, setOps] = useState<Operation[]>([])
  const [status, setStatus] = useState('')
  const [selected, setSelected] = useState<number | null>(initialSelected)
  const [detail, setDetail] = useState<OperationDetail | null>(null)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function loadList() {
    setErr('')
    try {
      setOps(await api.operations(status || undefined))
    } catch (e) {
      setErr(String(e))
    }
  }

  async function loadDetail(id: number) {
    setPlan(null)
    try {
      setDetail(await api.operation(id))
    } catch (e) {
      setErr(String(e))
    }
  }

  useEffect(() => {
    loadList()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status])

  useEffect(() => {
    if (selected != null) loadDetail(selected)
    else setDetail(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected])

  function select(id: number | null) {
    setSelected(id)
    onSelect(id)
  }

  async function act(fn: () => Promise<unknown>) {
    setBusy(true)
    setErr('')
    try {
      await fn()
      await loadList()
      if (selected != null) await loadDetail(selected)
    } catch (e) {
      setErr(String(e))
    } finally {
      setBusy(false)
    }
  }

  const op = detail?.operation

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Операции</h1>
          <div className="sub">Очередь, статусы, журнал и снимки</div>
        </div>
        <div className="flex">
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s || 'все статусы'}
              </option>
            ))}
          </select>
          <button className="btn" onClick={loadList}>
            Обновить
          </button>
        </div>
      </div>

      {err && <div className="banner err">{err}</div>}

      <div className="detail-grid">
        <div className="panel">
          <h2>Список</h2>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Тип</th>
                <th>Статус</th>
                <th>Попытки</th>
              </tr>
            </thead>
            <tbody>
              {ops.map((o) => (
                <tr
                  key={o.id}
                  className="clickable"
                  onClick={() => select(o.id)}
                  style={selected === o.id ? { background: '#eff6ff' } : undefined}
                >
                  <td className="mono">{o.id}</td>
                  <td>{o.type}</td>
                  <td>
                    <StatusBadge status={o.status} />
                  </td>
                  <td>
                    {o.attempts}/{o.max_attempts}
                  </td>
                </tr>
              ))}
              {ops.length === 0 && (
                <tr>
                  <td colSpan={4} className="muted">
                    Нет операций
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="panel">
          <h2>Детали операции</h2>
          {!op && <div className="muted">Выберите операцию слева.</div>}
          {op && (
            <>
              <div className="kv">
                <div className="k">ID</div>
                <div className="mono">{op.id}</div>
                <div className="k">Тип</div>
                <div>{op.type}</div>
                <div className="k">Статус</div>
                <div>
                  <StatusBadge status={op.status} /> {op.dry_run && <span className="badge slate">dry-run</span>}
                </div>
                <div className="k">Idempotency</div>
                <div className="mono">{op.idempotency_key}</div>
                <div className="k">Попытки</div>
                <div>
                  {op.attempts}/{op.max_attempts}
                </div>
                <div className="k">Подтверждение</div>
                <div>
                  {op.requires_approval
                    ? op.approved_at
                      ? `да — ${op.approved_by} (${fmt(op.approved_at)})`
                      : 'требуется'
                    : 'не требуется'}
                </div>
                {op.error && (
                  <>
                    <div className="k">Ошибка</div>
                    <div style={{ color: 'var(--red)' }}>{op.error}</div>
                  </>
                )}
                <div className="k">Создана</div>
                <div className="muted">{fmt(op.created_at)}</div>
              </div>

              <div className="btn-row" style={{ marginTop: 14 }}>
                <button
                  className="btn"
                  disabled={busy}
                  onClick={() => act(async () => setPlan(await api.dryRun(op.id)))}
                >
                  Dry-run превью
                </button>
                {op.status === 'awaiting_approval' && (
                  <button
                    className="btn primary"
                    disabled={busy}
                    onClick={() => act(() => api.approve(op.id, 'admin'))}
                  >
                    Подтвердить
                  </button>
                )}
                {['failed', 'dead', 'cancelled'].includes(op.status) && (
                  <button className="btn" disabled={busy} onClick={() => act(() => api.retry(op.id))}>
                    Повторить
                  </button>
                )}
                {!['succeeded', 'cancelled', 'dead', 'running'].includes(op.status) && (
                  <button
                    className="btn danger"
                    disabled={busy}
                    onClick={() => act(() => api.cancel(op.id))}
                  >
                    Отменить
                  </button>
                )}
              </div>

              {plan && (
                <div style={{ marginTop: 14 }}>
                  <h2>Превью (что будет сделано)</h2>
                  <div className="banner safe">
                    {plan.action} · {plan.summary}
                  </div>
                  <JsonView data={plan.after} />
                </div>
              )}

              <h2 style={{ marginTop: 16 }}>Payload</h2>
              <JsonView data={op.payload} />

              <h2 style={{ marginTop: 16 }}>Результат</h2>
              <JsonView data={op.result} />

              <h2 style={{ marginTop: 16 }}>Снимки (было / стало)</h2>
              {detail!.snapshots.length === 0 && <div className="muted">Нет снимков</div>}
              {detail!.snapshots.map((s) => (
                <div key={s.id} style={{ marginBottom: 10 }}>
                  <div className="muted">
                    {s.action} · {s.entity_ref}
                  </div>
                  <JsonView data={{ before: s.before, after: s.after }} />
                </div>
              ))}

              <h2 style={{ marginTop: 16 }}>Журнал</h2>
              <table>
                <tbody>
                  {detail!.logs.map((l) => (
                    <tr key={l.id}>
                      <td style={{ width: 70 }}>
                        <span className={`badge ${l.level === 'error' ? 'red' : 'slate'}`}>
                          {l.level}
                        </span>
                      </td>
                      <td>{l.message}</td>
                      <td className="muted right" style={{ width: 160 }}>
                        {fmt(l.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      </div>
    </>
  )
}
