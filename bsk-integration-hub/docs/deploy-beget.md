# Первый деплой на VPS Beget (встроенный терминал) — hub.bsk-group.ru

Пошаговый runbook для **чистого VPS Beget** через **встроенный веб-терминал**
(SSH с локального ПК пока не нужен). Цель: поднять сервис + Caddy/HTTPS и
проверить `https://hub.bsk-group.ru/health`. **Без боевых секретов Б24/МС, без
реальных вызовов, dry-run по умолчанию.**

> Все команды выполняются во встроенном терминале Beget (обычно под `root`).
> Если вы не root — добавляйте `sudo` перед docker-командами.

## Быстрый деплой одной командой

Вместо ручного ввода шагов 1–12 можно запустить готовый скрипт (безопасно:
mock + dry-run, без боевых секретов, идемпотентно). Под `root`:

```bash
cd /opt && curl -fsSLO https://raw.githubusercontent.com/talalayko-png/bitrix-admin-agent/main/bsk-integration-hub/scripts/beget-deploy.sh && bash beget-deploy.sh
```

Скрипт сам поставит Docker/утилиты, настроит firewall, клонирует репозиторий,
создаст `.env` с безопасными значениями, сгенерирует `ADMIN_API_TOKEN` (печатает
его — сохраните), поднимет сервис с Caddy/HTTPS и проверит `/health`.
Переопределить домен/почту: `DOMAIN=... ACME_EMAIL=... bash beget-deploy.sh`.

Ниже — те же шаги вручную, если нужен полный контроль.

---

## 1. Проверка Docker и docker compose

```bash
docker --version
docker compose version
```

Если команды не найдены — установите Docker:

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
docker compose version
```

## 2. Проверка IP сервера

```bash
hostname -I | awk '{print $1}'      # внутренний/основной IP
curl -s https://api.ipify.org; echo # внешний IP, как видит интернет
```

Запомните **внешний IP** — на него должна указывать DNS-запись домена.

## 3. Проверка DNS для hub.bsk-group.ru

```bash
getent hosts hub.bsk-group.ru || true
# или, если установлен dig:
dig +short hub.bsk-group.ru A
```

IP в ответе должен совпадать с внешним IP из шага 2. Если нет — заведите в DNS
домена `bsk-group.ru` **A-запись** `hub` → внешний IP сервера и подождите
распространения (обычно минуты, иногда до часа). **Без корректного DNS Caddy не
получит TLS-сертификат.**

## 4. Проверка портов 80/443

```bash
# Никто ли уже не слушает 80/443 (должно быть пусто до запуска):
ss -tlnp | grep -E ':80 |:443 ' || echo "80/443 свободны"

# Firewall: если используется ufw — откройте порты
if command -v ufw >/dev/null; then
  ufw allow 80/tcp; ufw allow 443/tcp; ufw deny 8000/tcp; ufw --force enable; ufw status
else
  echo "ufw не установлен — проверьте файрвол в панели Beget (открыть 80,443; закрыть 8000)"
fi
```

> В панели Beget также проверьте раздел «Файрвол/Брандмауэр» — порты 80 и 443
> должны быть открыты для входящих.

## 5. Клонирование репозитория

```bash
cd /opt
git clone https://github.com/talalayko-png/bitrix-admin-agent.git
cd bitrix-admin-agent/bsk-integration-hub
```

## 6. Создание .env без боевых секретов

```bash
cp .env.example .env
```

## 7. Генерация ADMIN_API_TOKEN и базовая настройка .env

```bash
ADMIN=$(openssl rand -hex 32)
sed -i "s|^ADMIN_API_TOKEN=.*|ADMIN_API_TOKEN=$ADMIN|" .env
sed -i "s|^DOMAIN=.*|DOMAIN=hub.bsk-group.ru|" .env
sed -i "s|^ACME_EMAIL=.*|ACME_EMAIL=admin@bsk-group.ru|" .env
sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=https://hub.bsk-group.ru|" .env
sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg://bsk:bsk@postgres:5432/bsk|" .env
sed -i "s|^QUEUE_BACKEND=.*|QUEUE_BACKEND=redis|" .env
sed -i "s|^REDIS_URL=.*|REDIS_URL=redis://redis:6379/0|" .env

# Предохранители безопасности — оставляем безопасные значения (на всякий случай форсируем):
sed -i "s|^DRY_RUN=.*|DRY_RUN=true|" .env
sed -i "s|^USE_MOCK_CONNECTORS=.*|USE_MOCK_CONNECTORS=true|" .env
sed -i "s|^ALLOW_REAL_API=.*|ALLOW_REAL_API=false|" .env

echo "СОХРАНИТЕ admin-токен (понадобится для панели): $ADMIN"
```

Проверка, что боевых секретов нет (должно быть пусто):

```bash
grep -E '^(MOYSKLAD_TOKEN|BITRIX24_OUTBOUND_WEBHOOK_URL|BITRIX24_INBOUND_WEBHOOK_SECRET)=.+' .env \
  && echo "⚠ есть заполненные секреты — очистите!" || echo "✓ боевых секретов нет"
```

## 8. Запуск docker compose (prod, с Caddy/HTTPS)

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Первый запуск собирает образ и тянет Postgres/Redis/Caddy — это занимает пару минут.

## 9. Проверка контейнеров

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

Должны быть `app`, `worker`, `redis`, `postgres`, `caddy` в состоянии `running`
(у `app`/`postgres`/`redis` — `healthy`).

## 10. Проверка логов

```bash
# app: должна примениться миграция и подняться uvicorn
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=50 app
# caddy: получение TLS-сертификата
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=50 caddy
```

(Следить в реальном времени: добавьте `-f`, выход — `Ctrl+C`.)

## 11. Проверка /health

```bash
# Изнутри сервера (минуя HTTPS):
curl -s http://localhost:8000/health; echo

# Снаружи, через домен и HTTPS (после выпуска сертификата):
curl -s https://hub.bsk-group.ru/health; echo
```

Ожидаемо: `{"status":"ok","dry_run":true,"real_api_enabled":false,"queue_backend":"redis",...}`.

Откройте в браузере `https://hub.bsk-group.ru/health` и `https://hub.bsk-group.ru/docs`.

## 12. Если Caddy не получил SSL

Симптомы: `https://...` не открывается, в логах `caddy` — ошибки ACME.

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=120 caddy
```

Проверьте по порядку:

1. **DNS** (шаг 3): `getent hosts hub.bsk-group.ru` → внешний IP сервера. Если не
   совпадает/пусто — поправьте A-запись и подождите.
2. **Порт 80 доступен из интернета** (Let's Encrypt проверяет по HTTP-01 на :80):
   ```bash
   ss -tlnp | grep ':80 '            # должен слушать docker-proxy/caddy
   curl -s http://hub.bsk-group.ru/health; echo   # должен ответить
   ```
   Если порт 80 закрыт файрволом Beget — откройте его (шаг 4).
3. **Нет конфликта на 80/443** с другим веб-сервером (nginx/apache):
   ```bash
   systemctl stop nginx apache2 2>/dev/null || true
   ```
4. **Rate limit Let's Encrypt** (много попыток): подождите час или временно
   проверьте без публичного TLS:
   ```bash
   # временный самоподписанный режим (только для проверки, не для прода):
   #   в Caddyfile замените первую строку email-блока и домен на ': , tls internal'
   ```
5. После исправления — перезапустите только Caddy:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml restart caddy
   docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=80 caddy
   ```

## 13. Безопасная остановка / откат

```bash
# Остановить сервис (данные Postgres сохраняются в volume):
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

# Запустить снова:
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Откат кода на предыдущую версию:
git log --oneline -5
git checkout <нужный_commit_или_тег>
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# ПОЛНОЕ удаление вместе с данными БД (ОСТОРОЖНО, необратимо):
# docker compose -f docker-compose.yml -f docker-compose.prod.yml down -v
```

---

# Диагностика SSH (почему не подключается с вашего ПК)

Цель — понять, проблема на **сервере**, в **файрволе** или в вашей **локальной сети**.

> **Если SSH с ПК не подключается — сначала запустите серверный скрипт** во
> встроенном терминале Beget. Он диагностирует SSH и добавляет **запасной порт
> 2222** (порт 22 при этом не трогает):
>
> ```bash
> cd /opt/bitrix-admin-agent/bsk-integration-hub && git pull && bash scripts/beget-server-diagnostics.sh
> ```
>
> Подробный разбор причин (ping/`kex … timed out`/VPN/Keenetic/провайдер) и
> проверка по порту 2222 — в [ssh-troubleshooting.md](./ssh-troubleshooting.md).

## A. Команды на сервере (встроенный терминал Beget)

```bash
# Слушает ли sshd порт 22:
ss -tlnp | grep ':22 ' || echo "sshd не слушает 22"

# Статус и журнал ssh:
systemctl status ssh 2>/dev/null || systemctl status sshd
journalctl -u ssh -n 50 --no-pager 2>/dev/null || journalctl -u sshd -n 50 --no-pager

# Конфиг: порт, вход root, пароли:
grep -Ei '^(Port|PermitRootLogin|PasswordAuthentication)' /etc/ssh/sshd_config

# Файрвол на сервере:
( command -v ufw >/dev/null && ufw status ) || iptables -L -n | grep -E '22|DROP|REJECT' || echo "правил нет"
```

Если `sshd` не запущен:
```bash
systemctl enable --now ssh 2>/dev/null || systemctl enable --now sshd
```
Если порт закрыт ufw:
```bash
ufw allow 22/tcp && ufw reload
```

> Также проверьте **файрвол в панели Beget** — порт 22 должен быть разрешён для
> входящих с вашего IP (или со всех).

## B. Команды в Windows PowerShell (ваш ПК)

Замените `SERVER_IP` на внешний IP из шага 2 (или используйте домен).

```powershell
# 1) DNS резолвится?
nslookup hub.bsk-group.ru

# 2) TCP до порта 22 и запасного 2222 открыт?
Test-NetConnection SERVER_IP -Port 22
Test-NetConnection SERVER_IP -Port 2222

# 3) Для сравнения — порт 443 (веб) открыт?
Test-NetConnection SERVER_IP -Port 443

# 4) Подробный лог подключения ssh (22 и запасной 2222):
ssh -v root@SERVER_IP
ssh -p 2222 root@SERVER_IP
```

## C. Как понять, где проблема

| Что наблюдаете | Вероятная причина |
|---|---|
| `Test-NetConnection :22` → **TcpTestSucceeded: False**, а `:443` → **True** | Порт 22 закрыт **файрволом** (Beget-панель/ufw) или sshd не слушает — это **сервер/файрвол** |
| И `:22`, и `:443` → False, `ping` не проходит | **Сеть/сервер**: неверный IP, сервер выключен, или весь трафик режется |
| `:22` открыт (True), но `ssh` пишет *Permission denied* | TCP в порядке → дело в **аутентификации**: логин/пароль/ключ или `PermitRootLogin`/`PasswordAuthentication` в sshd_config |
| `:22` открыт (True), но `ssh` пишет *Connection timed out* на этапе обмена | Промежуточный **файрвол/ISP** режет SSH-трафик |
| С телефона (раздача 4G) SSH работает, с рабочего ПК — нет | Блокирует **ваша локальная сеть / корпоративный файрвол / провайдер** |

Быстрый тест «это моя сеть?»: подключитесь к серверу по SSH **с телефона через
мобильный интернет** (раздача). Если работает — проблема в вашей локальной сети,
а не на сервере.

> Пока SSH чинится — весь первый деплой полностью выполняется через встроенный
> терминал Beget по разделам 1–13 выше.
