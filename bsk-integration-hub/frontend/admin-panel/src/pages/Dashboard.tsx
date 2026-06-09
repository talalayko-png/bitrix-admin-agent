import { useEffect, useState } from 'react'
import { api } from '../api'
import { StatusBadge } from '../components/StatusBadge'
import type { Dashboard as DashboardData } from '../types'
import { fmt } from '../util'

export default function Dashboard({ onOpenOperation }: { onOpenOperation: (id: number) => void }) {
  const [data, setData] = useState<DashboardData | null>(null)
  const [err, setErr] = useState('')
  const [dealId, setDealId] = useState('1001')
  const [stage, setStage] = useState('WON')
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')

  async function load() {
    setErr('')
    try {
      setData(await api.dashboard())
    } catch (e) {
      setErr(String(e))
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function simulate() {
    setBusy(true)
    setNote('')
    try {
      const res = await api.simulateDeal(dealId, stage)
      setNote(
        res.operation_ids.length
          ? `Создана операция #${res.operation_ids.join(', #')}`
          : 'Событие принято, но ни один процесс не сработал (возможно, процесс выключен)',
      )
      await load()
    } catch (e) {
      setNote(String(e))
    } finally {
      setBusy(false)
    }
  }

  if (err) return <div className="banner err">{err}</div>
  if (!data) return <div className="muted">Загрузка…</div>

  const f = data.flags
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Дашборд</h1>
          <div className="sub">Состояние интеграции Bitrix24 ↔ МойСклад</div>
        </div>
        <button className="btn" onClick={load}>
          Обновить
        </button>
      </div>

      {f.real_writes_enabled ? (
        <div className="banner err">
          ⚠ Включены РЕАЛЬНЫЕ ЗАПИСИ в Bitrix24/МойСклад. Операции изменяют боевые данные.
        </div>
      ) : f.real_reads_enabled ? (
        <div className="banner warn">
          ◐ Реальные ЧТЕНИЯ + dry-run: данные читаются из Bitrix24/МойСклад, но записи
          не выполняются (только планируются). Проверьте снимки операций.
        </div>
      ) : (
        <div className="banner safe">
          ✓ Безопасный режим: mock-коннекторы, реальных вызовов нет (dry_run=
          {String(f.dry_run)}).
        </div>
      )}

      <div className="cards">
        {Object.entries(data.counts).map(([k, v]) => (
          <div className="card" key={k}>
            <div className="label">{k}</div>
            <div className="value">{v}</div>
          </div>
        ))}
        <div className="card">
          <div className="label">Очередь</div>
          <div className="value">{data.queue_depth ?? '—'}</div>
        </div>
      </div>

      <div className="panel">
        <h2>Симуляция события Bitrix24 (без реального Bitrix24)</h2>
        <div className="row">
          <div className="field">
            <label>ID сделки</label>
            <input value={dealId} onChange={(e) => setDealId(e.target.value)} />
          </div>
          <div className="field">
            <label>Стадия</label>
            <input value={stage} onChange={(e) => setStage(e.target.value)} />
          </div>
          <button className="btn primary" disabled={busy} onClick={simulate}>
            {busy ? 'Отправка…' : 'Прогнать через процесс'}
          </button>
        </div>
        {note && <div className="banner safe" style={{ marginTop: 10 }}>{note}</div>}
      </div>

      <div className="panel">
        <h2>Последние операции</h2>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Тип</th>
              <th>Источник</th>
              <th>Статус</th>
              <th>Попытки</th>
              <th>Создана</th>
            </tr>
          </thead>
          <tbody>
            {data.recent.map((op) => (
              <tr key={op.id} className="clickable" onClick={() => onOpenOperation(op.id)}>
                <td className="mono">{op.id}</td>
                <td>{op.type}</td>
                <td>{op.source}</td>
                <td>
                  <StatusBadge status={op.status} />
                </td>
                <td>
                  {op.attempts}/{op.max_attempts}
                </td>
                <td className="muted">{fmt(op.created_at)}</td>
              </tr>
            ))}
            {data.recent.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">
                  Пока нет операций. Запустите симуляцию выше.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}
