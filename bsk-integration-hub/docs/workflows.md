# Процессы (workflows)

Workflow — это правило, превращающее входящее событие в операцию и описывающее,
что нужно сделать в целевой системе.

## Интерфейс

Каждый workflow наследует `src/workflows/base.py:Workflow` и реализует:

- `matches(envelope) -> bool` — относится ли событие к этому процессу;
- `build_draft(envelope) -> OperationDraft | None` — построить **идемпотентный**
  черновик операции (ключ строится так, что повтор события не создаёт дубль);
- `plan(ctx, payload) -> PlanResult` — **чистый** расчёт изменений (без записи):
  `action` (create/update/delete), `before`, `after`, `summary`;
- `apply(ctx, plan) -> dict` — реальная запись (вызывается **только** вне dry-run).

Базовый `execute` сам:
1) вызывает `plan`, 2) сохраняет снимок «было/стало», 3) в dry-run
останавливается и возвращает план, иначе вызывает `apply`.

## Пример: `deal_to_order`

`src/workflows/deal_to_order.py` — сделка Bitrix24 → заказ покупателя МойСклад.

- Триггер: события `ONCRMDEALADD/UPDATE` (и `deal.add/update`).
- `plan`: читает сделку и товарные позиции (через mock-коннектор Б24), строит
  payload заказа МС, ищет существующий заказ по `externalCode = deal_id` и решает
  create/update.
- В dry-run возвращает планируемый заказ и сумму; реальной записи нет.

## Готовые процессы

| Ключ                      | Триггер-события (Б24)                         | Действие в МойСклад            |
|---------------------------|----------------------------------------------|--------------------------------|
| `deal_to_order`           | `ONCRMDEALADD/UPDATE`, `deal.add/update`     | заказ покупателя (create/update) |
| `contact_to_counterparty` | `ONCRMCONTACTADD/UPDATE`, `contact.*`        | контрагент (create/update)     |
| `product_sync`            | `ONCRMPRODUCT*`, `product.*`, `catalog.*`    | товар (create/update)          |
| `payment_sync`            | `payment.add`, `deal.payment`                | входящий платёж (create)       |
| `create_supplier_docs`    | `ONCRMDYNAMICITEM*`, `item.*` (смарт-процесс) | заказ поставщику + счёт + приёмка (dry-run) |

`payment_sync` намеренно слушает отдельные события оплаты, чтобы не конфликтовать
с `deal_to_order` на обычном обновлении сделки.

## `create_supplier_docs` и dry-run превью

Процесс из смарт-процесса (СПА) «Снабжение» Bitrix24 готовит цепочку из **трёх**
документов в МойСклад (бизнес-сценарий — этап «Счёт получен / отправлен в оплату»):

1. **Заказ поставщику** (`purchaseorder`) — `applicable: true` (проведён), позиции
   с `wait: true` («ожидание»), `deliveryPlannedMoment` — из поля СПА «Плановая
   дата готовности у поставщика», `store` — из поля «Склад МС» материнской сделки;
2. **Счёт поставщика** (`invoicein`) — проведён, на основании заказа
   (ссылка `purchaseOrder`), `paymentPlannedMoment` — из «Дата оплаты поставщику»,
   `incomingNumber`/`incomingDate` — разбираются из текста «№ и дата счёта
   поставщика» («1021 от 2 июня 2026 г.», «7191 от 04.06.2026», …);
3. **Приёмка** (`supply`) — `applicable: false` (НЕ проведена), на основании
   заказа и счёта (`purchaseOrder` + `invoicesIn`), `moment` — план. дата приёмки.

Коды UF-полей СПА заданы дефолтами в `config.py` (выписаны инспектором с боевого
элемента 1066/481) и переопределяются через `.env`:
`SUPPLIER_DOCS_FIELD_READY_DATE`, `SUPPLIER_DOCS_FIELD_PAYMENT_DATE`,
`SUPPLIER_DOCS_FIELD_INVOICE_REF`, `SUPPLIER_DOCS_DEAL_STORE_FIELD` (код поля
«Склад МС» сделки; пока не настроен — берётся `MOYSKLAD_DEFAULT_STORE`).

В **dry-run** (по умолчанию) процесс ничего не пишет, а формирует подробный
предпросмотр в `result.after`:

- `received` — что пришло из Б24 (элемент, товарные позиции, материнская сделка);
- `validation` — проверка обязательных полей (`required_ok`), `warnings` — что
  не разобралось/не нашлось;
- `field_sources` — таблица «поле Б24 → атрибут МС» с сырыми и преобразованными
  значениями (для проверки маппинга владельцем);
- `mappings` — найденные соответствия Б24↔МС (организация, склад, контрагент, товары),
  с указанием источника (`mapping` — из таблицы соответствий, `lookup` — поиск в МС,
  `default` — склад по умолчанию);
- `documents` — какие документы и с какими payload’ами были бы созданы
  (`purchaseorder`, `invoicein`, `supply`) и какими ссылками они связываются;
- `writeback` — какие поля были бы записаны обратно в Б24.

Идемпотентность: ключ операции — `entityTypeId + itemId + create_supplier_docs +
target_stage`; если в элементе Б24 уже заполнены id документов МС, действие — `noop`.

## Reference-mappings (справочные соответствия)

Постоянные соответствия справочников Б24↔МС (товары, контрагенты, склады,
организации, типы цен/НДС) хранятся в таблице `reference_mappings` и управляются
через Admin API:

```
GET    /api/admin/reference-mappings?kind=product
POST   /api/admin/reference-mappings   {kind,b24_value,ms_type,ms_id,ms_name?,meta?}
DELETE /api/admin/reference-mappings/{id}
```

Workflow сначала ищет соответствие в этой таблице, затем — поиск в МС по
`externalCode`.

## Как добавить свой workflow

1. Создайте класс в `src/workflows/your_flow.py`, унаследовав `Workflow`.
2. Зарегистрируйте его в `src/workflows/registry.py` (`_WORKFLOWS`).
3. (Опц.) Добавьте тип операции в `APPROVAL_REQUIRED_FOR`, если он требует
   ручного подтверждения.
4. Включение/выключение — через `PUT /api/admin/workflows/{key}` или панель.

## Идемпотентность

`build_draft` обязан возвращать стабильный `idempotency_key`. Он уникален в БД:
повторный вебхук об одном событии вернёт существующую операцию, а не создаст
новую. При исполнении дополнительно берётся Redis-лок по ключу операции —
параллельное исполнение исключено.
