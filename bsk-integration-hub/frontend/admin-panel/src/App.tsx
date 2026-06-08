import { useState } from 'react'
import { api, ApiError, clearToken, getToken, setToken } from './api'
import Assistant from './pages/Assistant'
import Dashboard from './pages/Dashboard'
import Mappings from './pages/Mappings'
import Operations from './pages/Operations'
import Settings from './pages/Settings'
import Workflows from './pages/Workflows'

type View = 'dashboard' | 'operations' | 'mappings' | 'workflows' | 'settings' | 'assistant'

const NAV: { key: View; label: string; icon: string }[] = [
  { key: 'dashboard', label: 'Дашборд', icon: '▦' },
  { key: 'operations', label: 'Операции', icon: '⚙' },
  { key: 'mappings', label: 'Связки сущностей', icon: '↔' },
  { key: 'workflows', label: 'Процессы', icon: '⛓' },
  { key: 'settings', label: 'Настройки', icon: '⚑' },
  { key: 'assistant', label: 'AI-ассистент', icon: '✦' },
]

function TokenGate({ onAuthed }: { onAuthed: () => void }) {
  const [value, setValue] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit() {
    setBusy(true)
    setErr('')
    setToken(value.trim())
    try {
      await api.settings()
      onAuthed()
    } catch (e) {
      clearToken()
      setErr(
        e instanceof ApiError && e.status === 401
          ? 'Неверный токен'
          : 'Не удалось подключиться к API',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="gate">
      <div className="panel">
        <h1>BSK Integration Hub</h1>
        <p>Введите admin-токен (значение ADMIN_API_TOKEN из .env).</p>
        <div className="field">
          <label>Admin token</label>
          <input
            type="password"
            style={{ width: '100%' }}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
            placeholder="вставьте токен"
          />
        </div>
        {err && <div className="banner err">{err}</div>}
        <button className="btn primary" disabled={busy || !value} onClick={submit}>
          {busy ? 'Проверка…' : 'Войти'}
        </button>
      </div>
    </div>
  )
}

export default function App() {
  const [authed, setAuthed] = useState<boolean>(!!getToken())
  const [view, setView] = useState<View>('dashboard')
  const [selectedOp, setSelectedOp] = useState<number | null>(null)

  if (!authed) return <TokenGate onAuthed={() => setAuthed(true)} />

  function openOperation(id: number) {
    setSelectedOp(id)
    setView('operations')
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          BSK Hub
          <small>Bitrix24 ↔ МойСклад</small>
        </div>
        {NAV.map((n) => (
          <button
            key={n.key}
            className={`nav-item ${view === n.key ? 'active' : ''}`}
            onClick={() => setView(n.key)}
          >
            <span style={{ width: 16, display: 'inline-block' }}>{n.icon}</span>
            {n.label}
          </button>
        ))}
        <div className="spacer" />
        <button
          className="nav-item logout"
          onClick={() => {
            clearToken()
            setAuthed(false)
          }}
        >
          Выйти
        </button>
      </aside>

      <main className="content">
        {view === 'dashboard' && <Dashboard onOpenOperation={openOperation} />}
        {view === 'operations' && (
          <Operations initialSelected={selectedOp} onSelect={setSelectedOp} />
        )}
        {view === 'mappings' && <Mappings />}
        {view === 'workflows' && <Workflows />}
        {view === 'settings' && <Settings />}
        {view === 'assistant' && <Assistant />}
      </main>
    </div>
  )
}
