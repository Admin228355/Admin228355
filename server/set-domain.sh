#!/usr/bin/env bash
# TogetherForever: сменить публичный адрес сервера (например, когда поменялся
# адрес туннеля).
#
#   ./set-domain.sh новый-адрес.example.com
#
# Обновляет адрес в .env, в конфиге Centrifugo (allowed_origins) и в настройках
# PocketBase (адрес в письмах). Данные не трогает.
# Не забудь поменять и PB_URL в GitHub (Settings → Secrets and variables →
# Actions → Variables) и пересобрать APK: адрес зашит в приложение при сборке.
set -euo pipefail

NEW="${1:-}"
cd "$(dirname "$0")"

if [[ -z "$NEW" ]]; then
  echo "Использование: ./set-domain.sh <новый-адрес без https://>"
  exit 1
fi
if [[ ! -f .env ]]; then
  echo "Нет server/.env — сначала запусти ./install.sh."
  exit 1
fi

# Принимаем и «https://адрес/», и просто «адрес».
NEW="${NEW#https://}"
NEW="${NEW#http://}"
NEW="${NEW%%/*}"

sed -i "s/^DOMAIN=.*/DOMAIN=$NEW/" .env
set -a; . ./.env; set +a

sed -e "s/__CENTRIFUGO_TOKEN_HMAC__/$CENTRIFUGO_TOKEN_HMAC/" \
    -e "s/__CENTRIFUGO_API_KEY__/$CENTRIFUGO_API_KEY/" \
    -e "s/__DOMAIN__/$DOMAIN/" centrifugo.json.tmpl > data/centrifugo.json

# Caddy (в обычном режиме берёт адрес из DOMAIN) и Centrifugo перечитывают конфиг.
docker compose up -d --force-recreate caddy centrifugo

PB_URL=http://127.0.0.1:8090 PB_EMAIL="$ADMIN_EMAIL" PB_PASSWORD="$ADMIN_PASSWORD" \
  APP_URL="https://$DOMAIN" python3 bootstrap.py >/dev/null

echo "Готово: адрес сервера — https://$DOMAIN"
