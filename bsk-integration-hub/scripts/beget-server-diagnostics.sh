#!/usr/bin/env bash
# BSK Integration Hub — Beget server SSH diagnostics & safe preparation.
#
# Run as root in the Beget WEB terminal (not over SSH):
#   bash scripts/beget-server-diagnostics.sh
#
# SAFE & IDEMPOTENT. This script DOES NOT:
#   * disable or remove SSH port 22;
#   * change the root password;
#   * touch the Docker project / containers;
#   * delete anything.
# It only diagnoses and, additionally, opens firewall ports and adds a FALLBACK
# SSH port 2222 (keeping 22) so you can reach the server if 22 is blocked.

set -uo pipefail  # intentionally NOT -e: keep going through all diagnostics

ALT_PORT=2222
SSHD_DROPIN="/etc/ssh/sshd_config.d/99-custom-port.conf"
SSHD_BIN="$(command -v sshd || echo /usr/sbin/sshd)"

section() { printf '\n\033[1;34m== %s ==\033[0m\n' "$*"; }
ok()      { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn()    { printf '  \033[33m!\033[0m %s\n' "$*"; }
err()     { printf '  \033[31m✗\033[0m %s\n' "$*"; }
listens() { ss -tlnH "( sport = :$1 )" 2>/dev/null | grep -q . ; }

# ---------------------------------------------------------------- 1. user
section "1. Текущий пользователь"
id 2>/dev/null || true
if [ "$(id -u)" != "0" ]; then
  warn "скрипт запущен НЕ под root — изменения портов/файрвола могут не примениться (используйте sudo)"
fi

# ---------------------------------------------------------------- 2. ip
section "2. Внешний IP сервера"
EXT_IP="$(curl -fsS --max-time 10 https://api.ipify.org 2>/dev/null || true)"
if [ -n "${EXT_IP}" ]; then ok "внешний IP: ${EXT_IP}"; else warn "не удалось определить внешний IP"; fi
echo "  локальные адреса: $(hostname -I 2>/dev/null || true)"

# ---------------------------------------------------------------- 3. docker
section "3. Docker и docker compose"
if command -v docker >/dev/null 2>&1; then ok "docker: $(docker --version 2>/dev/null)"
else warn "docker не установлен (curl -fsSL https://get.docker.com | sh)"; fi
if docker compose version >/dev/null 2>&1; then ok "compose: $(docker compose version 2>/dev/null | head -1)"
else warn "docker compose plugin не найден"; fi

# ---------------------------------------------------------------- 4. ssh:22
section "4. Слушает ли SSH порт 22"
if listens 22; then ok "порт 22 слушается"; else err "порт 22 НЕ слушается"; fi

# ---------------------------------------------------------------- 5. ssh status
section "5. Статус ssh/sshd"
(systemctl status ssh --no-pager 2>/dev/null || systemctl status sshd --no-pager 2>/dev/null || true) | head -6

# ---------------------------------------------------------------- 6. ports
section "6. Активные порты 22/80/443/${ALT_PORT}"
ss -tlnp 2>/dev/null | grep -E ":(22|80|443|${ALT_PORT}) " || echo "  (совпадений нет)"

# ---------------------------------------------------------------- 7. firewall
section "7. Файрвол (ufw / iptables)"
if command -v ufw >/dev/null 2>&1; then
  ufw status verbose 2>/dev/null | head -20
else
  warn "ufw не установлен"
  iptables -S 2>/dev/null | grep -E "22|80|443|${ALT_PORT}|DROP|REJECT" || echo "  iptables: явных правил по портам нет"
fi

# ---------------------------------------------------------------- 8. open ports
section "8. Открыть порты 22, ${ALT_PORT}, 80, 443"
if command -v ufw >/dev/null 2>&1; then
  for p in 22 "${ALT_PORT}" 80 443; do
    ufw allow "${p}/tcp" >/dev/null 2>&1 && ok "ufw allow ${p}/tcp" || warn "не удалось ufw allow ${p}/tcp"
  done
else
  warn "ufw нет — откройте 22, ${ALT_PORT}, 80, 443 в панели Beget (раздел Файрвол)"
fi

# ---------------------------------------------------------------- 9. fallback port
section "9. Запасной SSH-порт ${ALT_PORT} (идемпотентно)"
mkdir -p /etc/ssh/sshd_config.d 2>/dev/null || true
if ! grep -qE '^[[:space:]]*Include[[:space:]]+/etc/ssh/sshd_config\.d/\*\.conf' /etc/ssh/sshd_config 2>/dev/null; then
  warn "в /etc/ssh/sshd_config нет Include для sshd_config.d — добавляю"
  printf '\nInclude /etc/ssh/sshd_config.d/*.conf\n' >> /etc/ssh/sshd_config
fi
if [ -f "${SSHD_DROPIN}" ] && grep -qE "^[[:space:]]*Port[[:space:]]+${ALT_PORT}\b" "${SSHD_DROPIN}"; then
  ok "порт ${ALT_PORT} уже настроен (${SSHD_DROPIN}) — не дублирую"
else
  cat > "${SSHD_DROPIN}" <<EOF
# Added by beget-server-diagnostics.sh — keep port 22 AND add a fallback port.
# Removing this file reverts to the default SSH port only.
Port 22
Port ${ALT_PORT}
EOF
  ok "записан ${SSHD_DROPIN} (Port 22 + Port ${ALT_PORT})"
fi

# ---------------------------------------------------------------- 10. sshd -t
section "10. Проверка конфигурации (sshd -t)"
SKIP_RELOAD=0
if "${SSHD_BIN}" -t 2>/tmp/sshd_t.err; then
  ok "sshd -t: конфигурация валидна"
else
  err "sshd -t: ошибка конфигурации:"; sed 's/^/      /' /tmp/sshd_t.err
  warn "перезапуск SSH ПРОПУСКАЮ (порт 22 продолжает работать как прежде)"
  SKIP_RELOAD=1
fi

# ---------------------------------------------------------------- 11. restart
section "11. Перезапуск SSH (безопасно — вы в веб-терминале, не по SSH)"
if [ "${SKIP_RELOAD}" = "0" ]; then
  # restart нужен, чтобы sshd начал слушать новый порт; веб-сессию Beget это не рвёт
  if systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null; then
    sleep 1; ok "ssh перезапущен"
  else
    warn "systemctl restart не сработал — пробую reload"
    systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || true
  fi
else
  warn "пропущено из-за ошибки sshd -t"
fi

# ---------------------------------------------------------------- 12. final
section "12. Итог: слушаются ли 22 и ${ALT_PORT}"
for p in 22 "${ALT_PORT}"; do
  if listens "${p}"; then ok "порт ${p} слушается"; else err "порт ${p} НЕ слушается"; fi
done

section "Готово — проверьте с вашего ПК (PowerShell)"
HOST="${EXT_IP:-SERVER_IP}"
echo "  Test-NetConnection ${HOST} -Port 22"
echo "  Test-NetConnection ${HOST} -Port ${ALT_PORT}"
echo "  ssh -v root@${HOST}"
echo "  ssh -p ${ALT_PORT} root@${HOST}"
echo
echo "Если 2222 подключается, а 22 — нет: ваша сеть/VPN/провайдер режет порт 22."
echo "См. docs/ssh-troubleshooting.md (раздел про Keenetic / VPN)."
