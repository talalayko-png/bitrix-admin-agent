import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Workflow } from '../types'

export default function Workflows() {
  const [rows, setRows] = useState<Workflow[]>([])
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState<string | null>(null)

  async function load() {
    setErr('')
    try {
      setRows(await api.workflows())
    } catch (e) {
      setErr(String(e))
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function toggle(wf: Workflow) {
    setBusy(wf.key)
    try {
      await api.updateWorkflow(wf.key, { enabled: !wf.enabled })
      await load()
    } catch (e) {
      setErr(String(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Процессы (workflow)</h1>
          <div className="sub">Правила синхронизации между системами</div>
        </div>
        <button className="btn" onClick={load}>
          Обновить
        </button>
      </div>

      {err && <div className="banner err">{err}</div>}

      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>Ключ</th>
              <th>Название</th>
              <th>Триггер</th>
              <th>Тип операции</th>
              <th>Статус</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((wf) => (
              <tr key={wf.key}>
                <td className="mono">{wf.key}</td>
                <td>{wf.name}</td>
                <td>{wf.trigger_source}</td>
                <td className="mono">{wf.type}</td>
                <td>
                  <span className={`badge ${wf.enabled ? 'green' : 'slate'}`}>
                    {wf.enabled ? 'включён' : 'выключен'}
                  </span>
                </td>
                <td className="right">
                  <button className="btn" disabled={busy === wf.key} onClick={() => toggle(wf)}>
                    {wf.enabled ? 'Выключить' : 'Включить'}
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">
                  Нет процессов
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}
