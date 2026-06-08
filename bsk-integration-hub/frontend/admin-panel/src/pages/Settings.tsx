import { useEffect, useState } from 'react'
import { api } from '../api'
import { JsonView } from '../components/JsonView'

export default function Settings() {
  const [data, setData] = useState<Record<string, unknown> | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    api
      .settings()
      .then(setData)
      .catch((e) => setErr(String(e)))
  }, [])

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Настройки</h1>
          <div className="sub">Текущие флаги конфигурации (только чтение)</div>
        </div>
      </div>

      {err && <div className="banner err">{err}</div>}

      <div className="banner warn">
        Значения задаются переменными окружения в <span className="mono">.env</span> и применяются
        при перезапуске. Секреты (токены) здесь не отображаются.
      </div>

      <div className="panel">
        <h2>Конфигурация</h2>
        <JsonView data={data} />
      </div>

      <div className="panel">
        <h2>Предохранители исходящих вызовов</h2>
        <p className="muted">
          Реальные вызовы к Bitrix24/МойСклад выполняются только при одновременном
          <span className="mono"> allow_real_api=true</span>,
          <span className="mono"> use_mock_connectors=false</span> и
          <span className="mono"> dry_run=false</span>. По умолчанию все три предохранителя в
          безопасном положении.
        </p>
      </div>
    </>
  )
}
