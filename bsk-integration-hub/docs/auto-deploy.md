# Авто-деплой (GitHub Actions → Beget VPS)

При пуше в `main` (и по кнопке «Run workflow») GitHub Actions заходит на сервер по
SSH и обновляет сервис: `git reset --hard origin/main` + `docker compose up -d
--build`. Файл `.env` на сервере **не трогается** (ваши секреты/режим сохраняются),
реальные вызовы/записи не включаются.

> Доступ получает **автоматизация с ограниченным ключом**, а не человек. Боевых
> секретов в коде нет — только в GitHub Secrets и в серверном `.env`.

## Предусловия

1. Сервер уже развёрнут один раз через `scripts/beget-deploy.sh` (есть
   `/opt/bitrix-admin-agent` и `.env`).
2. На сервере работает Docker и стек поднимается (см. `docs/deploy-beget.md`).

## Шаг 1. Создать отдельный deploy-ключ

На любой машине (или прямо в терминале сервера) сгенерируйте **отдельную**
ключевую пару только для деплоя:

```bash
ssh-keygen -t ed25519 -C "github-deploy-bsk" -f deploy_key -N ""
# создаст deploy_key (приватный) и deploy_key.pub (публичный)
```

## Шаг 2. Разрешить ключ на сервере

Добавьте **публичный** ключ в authorized_keys пользователя деплоя (root):

```bash
# на сервере (терминал Beget), вставив содержимое deploy_key.pub:
mkdir -p /root/.ssh && chmod 700 /root/.ssh
echo "СОДЕРЖИМОЕ_deploy_key.pub" >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
```

## Шаг 3. Добавить секреты в GitHub

Репозиторий → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Значение |
|---|---|
| `BEGET_SSH_HOST` | `45.67.58.89` (или `hub.bsk-group.ru`) |
| `BEGET_SSH_USER` | `root` |
| `BEGET_SSH_KEY` | **приватный** ключ — всё содержимое файла `deploy_key` |
| `BEGET_SSH_PORT` | (опц.) `22` или `2222` |

> `BEGET_SSH_KEY` — это приватный ключ. Он хранится зашифрованным в GitHub Secrets
> и не виден в логах. Не коммитьте его в репозиторий.

## Шаг 4. (Опционально) Environment protection

В **Settings → Environments → production** можно включить ручное подтверждение
деплоя (required reviewers) — тогда каждый авто-деплой будет ждать вашего «Approve».

## Как это работает

- **Триггер**: push в `main` или ручной запуск (вкладка **Actions → Deploy →
  Run workflow**).
- Раннер по SSH выполняет `scripts/beget-update.sh` на сервере: тянет свежий
  `main`, пересобирает и перезапускает контейнеры (миграции применяются на старте
  `app`). `.env` не изменяется.
- **Без секретов** workflow завершается успешно и просто пропускает деплой
  (зелёный no-op) — удобно, пока вы не настроили доступ.

## Безопасность

- Отдельный ключ только для деплоя; при компрометации легко отозвать (удалить
  строку из `authorized_keys` и секрет в GitHub).
- `known_hosts` заполняется через `ssh-keyscan` (TOFU). Для строгой проверки
  можно заранее зафиксировать host key сервера.
- Авто-деплой обновляет **только код**; реальные секреты Б24/МС остаются в
  серверном `.env` под вашим контролем; предохранители (`DRY_RUN` и т.д.) не
  переключаются автоматически.

## Как отключить

- Уберите секреты `BEGET_SSH_*` (workflow начнёт пропускать деплой), **или**
- удалите/переименуйте `.github/workflows/deploy.yml`, **или**
- в Environment `production` включите обязательное подтверждение.

## Проверка

После настройки секретов нажмите **Actions → Deploy → Run workflow** (ветка
`main`). В логах должно быть `Deploying to root@…` и в конце `== health ==` с
ответом `/health`. Затем — `https://hub.bsk-group.ru/health`.
