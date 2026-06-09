import { useState } from 'react'
import { api } from '../api'
import type { AssistantAnswer } from '../types'

export default function Assistant() {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<AssistantAnswer | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function ask() {
    setBusy(true)
    setErr('')
    try {
      setAnswer(await api.assistant(question))
    } catch (e) {
      setErr(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>AI-ассистент</h1>
          <div className="sub">Объяснение ошибок и подсказки по интеграции</div>
        </div>
      </div>

      <div className="banner warn">
        Плейсхолдер: ассистент пока не подключён. Здесь появятся объяснения ошибок синхронизации,
        подсказки по маппингу и генерация правил workflow.
      </div>

      <div className="panel">
        <div className="field">
          <label>Вопрос</label>
          <textarea
            style={{ width: '100%', minHeight: 80 }}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Например: почему операция #12 завершилась ошибкой?"
          />
        </div>
        <button className="btn primary" disabled={busy || !question} onClick={ask}>
          {busy ? 'Запрос…' : 'Спросить'}
        </button>
        {err && <div className="banner err" style={{ marginTop: 12 }}>{err}</div>}
        {answer && (
          <div className="banner safe" style={{ marginTop: 12 }}>
            <strong>{answer.enabled ? 'Ответ' : 'Ассистент (демо)'}:</strong> {answer.answer}
          </div>
        )}
      </div>
    </>
  )
}
