# Прод-деплой и подключение Bitrix24 / МойСклад

Рунбук для запуска на **своём VPS** (Docker + Caddy с авто-HTTPS) и **поэтапного**,
безопасного перехода к реальным вызовам. Первые реальные вызовы делаем на
**песочнице/тестовом портале**.

> ⚠️ Секреты вписываются **только** в `.env` на сервере. Не коммитьте `.env`,
> не пересылайте боевые токены в переписке.

---

## 0. Что понадобится

- VPS (2 vCPU / 2–4 ГБ ОЗУ достаточно для старта), Ubuntu 22.04+.
- Домен и доступ к DNS (заведём A-запись на IP сервера).
- Тестовый портал **Bitrix24** и тестовый аккаунт **МойСклад** (для первых вызовов).

## 1. Подготовка сервера

```bash
# Docker + compose plugin
curl -fsSL https://get.docker.com | sh

# Код
git clone <repo-url> && cd bitrix-admin-agent/bsk-integration-hub
cp .env.example .env
```

DNS: добавьте `A`-запись `hub.example.com` → IP сервера. Откройте порты 80 и 443.
Порт `8000` (app) закройте от интернета — наружу смотрит только Caddy:

```bash
ufw allow 80,443/tcp && ufw deny 8000/tcp && ufw enable
```

## 2. Заполнение `.env`

```bash
# Сгенерируйте админ-токен
openssl rand -hex 32
```

Минимум для прод-запуска:

```ini
APP_ENV=prod
LOG_JSON=true
ADMIN_API_TOKEN=<сгенерированный токен>
CORS_ORIGINS=https://hub.example.com

DATABASE_URL=postgresql+psycopg://bsk:bsk@postgres:5432/bsk
QUEUE_BACKEND=redis
REDIS_URL=redis://redis:6379/0

# HTTPS (Caddy)
DOMAIN=hub.example.com
ACME_EMAIL=you@example.com

# Безопасный старт — всё на моках
DRY_RUN=true
USE_MOCK_CONNECTORS=true
ALLOW_REAL_API=false

# Подписи вебхуков (заполним на шагах 5–6)
BITRIX24_INBOUND_WEBHOOK_SECRET=
MOYSKLAD_INBOUND_WEBHOOK_SECRET=
# Доступы к API (заполним на шагах 5–6, на песочнице)
BITRIX24_OUTBOUND_WEBHOOK_URL=
MOYSKLAD_TOKEN=
```

## 3. Запуск (с HTTPS)

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Поднимутся `app` (с `alembic upgrade head`), `worker`, `redis`, `postgres`, `caddy`.
Caddy сам получит TLS-сертификат для `DOMAIN`.

## 4. Проверка инфраструктуры (режим моков)

```bash
curl https://hub.example.com/health
# {"status":"ok","dry_run":true,"queue_backend":"redis",...}
```

- Откройте admin-панель (раздайте `frontend/admin-panel/dist` статикой или
  локально через `npm run dev` с `VITE_API_BASE=https://hub.example.com`).
- На дашборде — зелёный баннер «Безопасный режим». Нажмите «Прогнать через
  процесс» — операция должна пройти на моках.

## 5. Подключение Bitrix24 (на тестовом портале)

1. **Исходящий вебхук (наши вызовы в Б24).** В Б24: *Разработчикам → Другое →
   Входящий вебхук* → выдайте права CRM → скопируйте URL вида
   `https://<portal>.bitrix24.ru/rest/<user>/<token>/`. Впишите его в
   `BITRIX24_OUTBOUND_WEBHOOK_URL`.
2. **События из Б24 к нам.** *Разработчикам → Исходящий вебхук*: события
   `ONCRMDEALUPDATE`, `ONCRMCONTACTUPDATE` и т.п., обработчик —
   `https://hub.example.com/webhooks/bitrix24`. Скопируйте `application_token`
   в `BITRIX24_INBOUND_WEBHOOK_SECRET`.

> ⚠️ Б24 присылает в теле `application_token` (не HMAC). Сверку входящих под эту
> схему добавляем отдельным PR (см. «Известные ограничения»).

## 6. Подключение МойСклад (на тестовом аккаунте)

1. **Токен API.** В МС: *Настройки → API* → выдать токен. Впишите в `MOYSKLAD_TOKEN`.
2. **Вебхуки из МС к нам.** *Настройки → Вебхуки* → URL
   `https://hub.example.com/webhooks/moysklad`, нужные сущности/действия.
   Секрет (если используете) — в `MOYSKLAD_INBOUND_WEBHOOK_SECRET`.

## 7. Этап А — «реальные ЧТЕНИЯ + dry-run» (без записи)

Самый важный шаг: читаем живые данные, но **ничего не пишем**.

```ini
ALLOW_REAL_API=true
USE_MOCK_CONNECTORS=false
DRY_RUN=true          # записи по-прежнему запрещены guard_write
```

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

- Дашборд: жёлтый баннер «Реальные ЧТЕНИЯ + dry-run».
- Триггерните событие в Б24 (или `POST /api/admin/simulate/deal`) и в панели
  откройте операцию → **снимок «было/стало»**. Убедитесь, что планируемый
  payload МС корректен на реальных данных. Записи в МС нет.

## 8. Этап Б — записи на ПЕСОЧНИЦЕ

Когда снимки выглядят правильно, включаем записи **на тестовом аккаунте**:

```ini
DRY_RUN=false
APPROVAL_REQUIRED_FOR=order_delete,invoice_void   # опасное — только вручную
```

- Дашборд: красный баннер «Реальные ЗАПИСИ».
- Прогоните один процесс (`deal_to_order`), проверьте созданный объект в МС.
- Операции из `APPROVAL_REQUIRED_FOR` подтверждаются вручную в панели.

## 9. Этап В — боевые данные, постепенно

- Переключите доступы на боевой портал/аккаунт.
- Включайте процессы по одному (вкл/выкл в разделе «Процессы»).
- Держите approval gate на необратимых операциях.

## 10. Эксплуатация

**Бэкап Postgres (cron):**
```bash
docker compose exec -T postgres pg_dump -U bsk bsk | gzip > backup_$(date +%F).sql.gz
```
**Обновление:**
```bash
git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```
**Логи:** `docker compose logs -f app worker`.

## Чеклист безопасности

- [ ] `ADMIN_API_TOKEN` — длинный случайный, `.env` не в git.
- [ ] Порт 8000 закрыт фаерволом, наружу только 80/443 (Caddy).
- [ ] Первые реальные вызовы — на песочнице, через этап «чтения + dry-run».
- [ ] `APPROVAL_REQUIRED_FOR` покрывает необратимые операции.
- [ ] Бэкапы БД настроены.

## Известные ограничения (готовим отдельным PR)

Реальные коннекторы рабочие по структуре и покрыты офлайн-тестами, но перед
боевыми **записями** нужно довести:

1. **Боевой маппинг payload’ов МойСклад** — `customerorder/counterparty/product`
   требуют ссылок `meta`/href (организация, контрагент, склад, типы цен).
2. **Сверка входящих вебхуков** под реальные схемы: Б24 (`application_token`),
   МС (секрет/IP).
3. **Лимиты и пагинация** реальных API (429/backoff, постраничные выборки).

До этого момента держите процессы записи в `DRY_RUN=true` (этап А) и проверяйте
снимки. См. `ROADMAP.md`.
