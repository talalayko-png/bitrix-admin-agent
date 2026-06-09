import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Mapping } from '../types'
import { fmt } from '../util'

export default function Mappings() {
  const [rows, setRows] = useState<Mapping[]>([])
  const [err, setErr] = useState('')
  const [form, setForm] = useState({ b24_type: 'deal', b24_id: '', ms_type: 'customerorder', ms_id: '' })

  async function load() {
    setErr('')
    try {
      setRows(await api.mappings())
    } catch (e) {
      setErr(String(e))
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function create() {
    try {
      await api.createMapping({ ...form, meta: null })
      setForm({ ...form, b24_id: '', ms_id: '' })
      await load()
    } catch (e) {
      setErr(String(e))
    }
  }

  async function remove(id: number) {
    try {
      await api.deleteMapping(id)
      await load()
    } catch (e) {
      setErr(String(e))
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Связки сущностей</h1>
          <div className="sub">Соответствие объектов Bitrix24 ↔ МойСклад</div>
        </div>
        <button className="btn" onClick={load}>
          Обновить
        </button>
      </div>

      {err && <div className="banner err">{err}</div>}

      <div className="panel">
        <h2>Добавить связку</h2>
        <div className="row">
          <div className="field">
            <label>Тип Б24</label>
            <input value={form.b24_type} onChange={(e) => setForm({ ...form, b24_type: e.target.value })} />
          </div>
          <div className="field">
            <label>ID Б24</label>
            <input value={form.b24_id} onChange={(e) => setForm({ ...form, b24_id: e.target.value })} />
          </div>
          <div className="field">
            <label>Тип МС</label>
            <input value={form.ms_type} onChange={(e) => setForm({ ...form, ms_type: e.target.value })} />
          </div>
          <div className="field">
            <label>ID МС</label>
            <input value={form.ms_id} onChange={(e) => setForm({ ...form, ms_id: e.target.value })} />
          </div>
          <button className="btn primary" disabled={!form.b24_id || !form.ms_id} onClick={create}>
            Добавить
          </button>
        </div>
      </div>

      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Bitrix24</th>
              <th>МойСклад</th>
              <th>Создана</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m) => (
              <tr key={m.id}>
                <td className="mono">{m.id}</td>
                <td>
                  {m.b24_type}:<span className="mono">{m.b24_id}</span>
                </td>
                <td>
                  {m.ms_type}:<span className="mono">{m.ms_id}</span>
                </td>
                <td className="muted">{fmt(m.created_at)}</td>
                <td className="right">
                  <button className="btn danger" onClick={() => remove(m.id)}>
                    Удалить
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  Нет связок
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}
