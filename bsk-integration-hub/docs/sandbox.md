# Безопасная обкатка на песочнице (реальные чтения + dry-run)

Цель — прогнать весь конвейер `create_supplier_docs` на **живых данных** песочницы
Bitrix24/МойСклад, ничего не создавая и не записывая. Все записи заблокированы
предохранителем `guard_write`, пока `DRY_RUN=true`.

## 1. Включить реальные ЧТЕНИЯ (без записи)

В `.env` на сервере:

```ini
ALLOW_REAL_API=true
USE_MOCK_CONNECTORS=false
DRY_RUN=true            # записи запрещены (guard_write)
```

На дашборде появится жёлтый баннер «Реальные ЧТЕНИЯ + dry-run».

## 2. Подключить песочницу Bitrix24

```ini
BITRIX24_OUTBOUND_WEBHOOK_URL=https://<portal>.bitrix24.ru/rest/<user>/<token>/
BITRIX24_INBOUND_WEBHOOK_SECRET=<application_token исходящего вебхука>
SUPPLIER_DOCS_ENTITY_TYPE_ID=<typeId вашего смарт-процесса>
SUPPLIER_DOCS_TARGET_STAGE=<id целевой стадии или пусто>
BITRIX24_WRITEBACK_PURCHASEORDER_FIELD=ufCrm_...   # куда писать id заказа поставщику
BITRIX24_WRITEBACK_INVOICEIN_FIELD=ufCrm_...       # куда писать id счёта
```

Исходящий вебхук смарт-процесса (`ONCRMDYNAMICITEMUPDATE`) направьте на
`https://hub.example.com/webhooks/bitrix24`. Хаб проверит `application_token`,
нормализует payload (`entityTypeId/itemId/stageId`) и поставит операцию в очередь.

## 3. Подключить песочницу МойСклад

```ini
MOYSKLAD_TOKEN=<токен песочницы>
MOYSKLAD_DEFAULT_ORGANIZATION=<имя организации>
MOYSKLAD_DEFAULT_STORE=<имя склада>
MOYSKLAD_INBOUND_WEBHOOK_SECRET=<секрет, если используете вебхуки МС>
```

## 4. Завести соответствия справочников

Через Admin API (или панель) добавьте `reference-mappings` для товаров,
контрагентов, складов, организаций:

```bash
curl -X POST https://hub.example.com/api/admin/reference-mappings \
  -H "Authorization: Bearer $ADMIN_API_TOKEN" -H 'Content-Type: application/json' \
  -d '{"kind":"counterparty","b24_value":"<companyId Б24>","ms_type":"counterparty","ms_id":"<id МС>"}'
```

Workflow сначала смотрит в эту таблицу, затем ищет в МС по `externalCode`.

## 5. Проверить dry-run

Переведите элемент смарт-процесса на целевую стадию (или дождитесь события).
В админ-панели откройте операцию → раздел **результат/снимок**. В `result.after`:

- `received` — данные из Б24;
- `validation.required_ok` — пройдены ли обязательные поля;
- `mappings` — что сопоставилось (и откуда: `mapping`/`lookup`);
- `documents` — какие документы и payload’ы **были бы** отправлены в МС;
- `writeback` — какие поля **были бы** записаны в Б24.

Ничего при этом не создаётся и не записывается.

## 6. Какие записи заблокированы

Пока `DRY_RUN=true` — **все**: создание заказа поставщику/счёта, запись id обратно
в Б24. Приёмка (`supply`) не создаётся вообще (отдельный будущий процесс).

## 7. Чек-лист перед первым write-тестом

- [ ] dry-run превью корректно: правильные организация/склад/контрагент/товары;
- [ ] `required_ok=true` на реальных элементах;
- [ ] заведены reference-mappings для всех товаров/контрагентов;
- [ ] подтверждены коды UF-полей `BITRIX24_WRITEBACK_*` и обязательные поля МС;
- [ ] резервная копия данных песочницы.

Только после этого включайте записи на **песочнице**: `DRY_RUN=false` (красный
баннер). Опасные операции держите в `APPROVAL_REQUIRED_FOR`.
