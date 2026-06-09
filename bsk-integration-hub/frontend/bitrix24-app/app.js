// Thin Bitrix24 placement widget. All business logic lives in the backend;
// this page only reads/triggers operations via the admin API.

const LS_BASE = 'bsk_widget_api_base'
const LS_TOKEN = 'bsk_widget_token'

const $ = (id) => document.getElementById(id)

function apiBase() {
  return (localStorage.getItem(LS_BASE) || 'http://localhost:8000').replace(/\/$/, '')
}
function token() {
  return localStorage.getItem(LS_TOKEN) || ''
}

async function apiFetch(path, opts = {}) {
  const res = await fetch(apiBase() + path, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token()}`,
      ...(opts.headers || {}),
    },
  })
  const text = await res.text()
  const data = text ? JSON.parse(text) : null
  if (!res.ok) throw new Error((data && data.detail) || res.statusText)
  return data
}

function badge(status) {
  const map = {
    succeeded: 'green',
    failed: 'red',
    dead: 'red',
    awaiting_approval: 'amber',
    queued: 'blue',
    running: 'blue',
    pending: 'slate',
    cancelled: 'slate',
  }
  return `<span class="badge ${map[status] || 'slate'}">${status}</span>`
}

function renderError(msg) {
  $('status').innerHTML = `<div class="banner err">${msg}</div>`
}

async function loadStatus() {
  const dealId = $('deal-id').value.trim()
  if (!token()) {
    renderError('Укажите admin token в настройках.')
    return
  }
  try {
    const ops = await apiFetch('/api/admin/operations?status=')
    const mine = ops.filter(
      (o) => o.type === 'deal_to_order' && String(o.payload.deal_id) === dealId,
    )
    if (mine.length === 0) {
      $('status').innerHTML = `<div class="muted">Операций по сделке ${dealId} ещё нет. Нажмите «Синхронизировать».</div>`
      return
    }
    $('status').innerHTML = mine
      .map(
        (o) => `
        <div class="op">
          <div>Операция <span class="mono">#${o.id}</span> ${badge(o.status)} ${o.dry_run ? '<span class="badge slate">dry-run</span>' : ''}</div>
          <div class="muted">${o.result && o.result.summary ? o.result.summary : o.type}</div>
          ${o.error ? `<div class="err">${o.error}</div>` : ''}
          <div class="actions">
            <button class="btn" data-act="dry" data-id="${o.id}">Dry-run</button>
            ${['failed', 'dead', 'cancelled'].includes(o.status) ? `<button class="btn" data-act="retry" data-id="${o.id}">Повторить</button>` : ''}
            ${o.status === 'awaiting_approval' ? `<button class="btn primary" data-act="approve" data-id="${o.id}">Подтвердить</button>` : ''}
          </div>
        </div>`,
      )
      .join('')
    bindActions()
  } catch (e) {
    renderError(String(e.message || e))
  }
}

function bindActions() {
  document.querySelectorAll('[data-act]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = btn.getAttribute('data-id')
      const act = btn.getAttribute('data-act')
      try {
        if (act === 'dry') {
          const plan = await apiFetch(`/api/admin/operations/${id}/dry-run`, { method: 'POST' })
          alert(`${plan.action}: ${plan.summary}`)
        } else if (act === 'retry') {
          await apiFetch(`/api/admin/operations/${id}/retry`, { method: 'POST' })
          await loadStatus()
        } else if (act === 'approve') {
          await apiFetch(`/api/admin/operations/${id}/approve`, {
            method: 'POST',
            body: JSON.stringify({ approved_by: 'b24-widget' }),
          })
          await loadStatus()
        }
      } catch (e) {
        renderError(String(e.message || e))
      }
    })
  })
}

async function sync() {
  const dealId = $('deal-id').value.trim()
  try {
    await apiFetch('/api/admin/simulate/deal', {
      method: 'POST',
      body: JSON.stringify({ deal_id: dealId, stage: 'WON' }),
    })
    await loadStatus()
  } catch (e) {
    renderError(String(e.message || e))
  }
}

function initConfigUI() {
  $('api-base').value = localStorage.getItem(LS_BASE) || ''
  $('api-token').value = localStorage.getItem(LS_TOKEN) || ''
  $('cfg-toggle').addEventListener('click', () => $('config').classList.toggle('hidden'))
  $('save-cfg').addEventListener('click', () => {
    localStorage.setItem(LS_BASE, $('api-base').value.trim())
    localStorage.setItem(LS_TOKEN, $('api-token').value.trim())
    $('config').classList.add('hidden')
    loadStatus()
  })
  $('sync').addEventListener('click', sync)
  $('refresh').addEventListener('click', loadStatus)
}

// Try to read the deal id from the Bitrix24 placement, if embedded.
function tryBitrixPlacement() {
  try {
    if (typeof BX24 !== 'undefined' && BX24.init) {
      BX24.init(() => {
        const info = BX24.placement && BX24.placement.info && BX24.placement.info()
        const id = info && info.options && info.options.ID
        if (id) {
          $('deal-id').value = String(id)
          loadStatus()
        }
      })
    }
  } catch (_) {
    /* not embedded — manual mode */
  }
}

initConfigUI()
tryBitrixPlacement()
if (token()) loadStatus()
