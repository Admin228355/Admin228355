#!/usr/bin/env bash
# TogetherForever: установка сервера одной командой (Ubuntu/Debian).
#
#   git clone <репозиторий> togetherforever
#   cd togetherforever/server
#   sudo ./install.sh твой-домен.duckdns.org твоя@почта
#
# Домен должен уже смотреть на этот сервер (A-запись), а порты 80 и 443 —
# быть открыты: сертификат HTTPS Caddy выпустит сам.
set -euo pipefail

DOMAIN="${1:-}"
ADMIN_EMAIL="${2:-}"
# Репозиторий, где лежат релизы APK (для ссылок «скачать» на страницах сервера).
REPO_URL="${REPO_URL:-https://github.com/Admin228355/Admin228355}"
cd "$(dirname "$0")"

if [[ -z "$DOMAIN" || -z "$ADMIN_EMAIL" ]]; then
  echo "Использование: sudo ./install.sh <домен> <почта администратора>"
  exit 1
fi
if [[ $EUID -ne 0 ]]; then
  echo "Запусти через sudo."
  exit 1
fi

say() { printf '\n\033[1;35m==> %s\033[0m\n' "$*"; }

# Образы Ubuntu в Oracle Cloud закрывают всё, кроме SSH, прямо в iptables —
# даже когда порты открыты в панели облака. Открываем 80 и 443.
if command -v iptables >/dev/null 2>&1; then
  for port in 80 443; do
    iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null \
      || iptables -I INPUT 1 -p tcp --dport "$port" -j ACCEPT
  done
  iptables -C INPUT -p udp --dport 443 -j ACCEPT 2>/dev/null \
    || iptables -I INPUT 1 -p udp --dport 443 -j ACCEPT
  command -v netfilter-persistent >/dev/null 2>&1 && netfilter-persistent save || true
fi

if ! command -v docker >/dev/null 2>&1; then
  say "Ставлю Docker"
  curl -fsSL https://get.docker.com | sh
fi
command -v python3 >/dev/null 2>&1 || { apt-get update && apt-get install -y python3; }

if [[ ! -f .env ]]; then
  say "Генерирую секреты"
  rnd() { openssl rand -hex 32; }
  ADMIN_PASSWORD="$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)"
  cat > .env <<ENV
DOMAIN=$DOMAIN
REPO_URL=$REPO_URL
ADMIN_EMAIL=$ADMIN_EMAIL
ADMIN_PASSWORD=$ADMIN_PASSWORD
POSTGRES_PASSWORD=$(rnd)
CENTRIFUGO_API_KEY=$(rnd)
CENTRIFUGO_TOKEN_HMAC=$(rnd)
ENV
  chmod 600 .env
fi
set -a; . ./.env; set +a

mkdir -p data/pb_data data/postgres data/caddy
sed -e "s/__CENTRIFUGO_TOKEN_HMAC__/$CENTRIFUGO_TOKEN_HMAC/" \
    -e "s/__CENTRIFUGO_API_KEY__/$CENTRIFUGO_API_KEY/" \
    -e "s/__DOMAIN__/$DOMAIN/" centrifugo.json.tmpl > data/centrifugo.json

say "Собираю образы (первый раз — несколько минут)"
docker compose build

say "Запускаю базу и PocketBase"
docker compose up -d postgres pocketbase
for _ in $(seq 60); do
  curl -fsS http://127.0.0.1:8090/api/health >/dev/null 2>&1 && break
  sleep 2
done

say "Администратор PocketBase"
docker compose exec -T pocketbase /pb/pocketbase superuser upsert \
  "$ADMIN_EMAIL" "$ADMIN_PASSWORD" --dir /pb/pb_data

say "Схема PocketBase"
PB_URL=http://127.0.0.1:8090 PB_EMAIL="$ADMIN_EMAIL" PB_PASSWORD="$ADMIN_PASSWORD" \
  APP_URL="https://$DOMAIN" python3 bootstrap.py

say "Схема Postgres"
python3 hotpath_schema.py | docker compose exec -T postgres \
  psql -q -v ON_ERROR_STOP=1 -U togetherforever -d togetherforever

say "Идентификаторы коллекций для hotpath"
sed -i '/^CID_/d' .env
PB_URL=http://127.0.0.1:8090 PB_EMAIL="$ADMIN_EMAIL" PB_PASSWORD="$ADMIN_PASSWORD" \
  python3 collection_ids.py >> .env

say "Запускаю всё"
docker compose up -d

say "Готово!"
cat <<DONE

  Сервер:        https://$DOMAIN
  Админка:       https://$DOMAIN/_/
  Логин админки: $ADMIN_EMAIL
  Пароль:        $ADMIN_PASSWORD   (лежит в server/.env)

  Собери приложение под этот сервер:
    в GitHub: Settings → Secrets and variables → Actions → Variables →
    PB_URL = https://$DOMAIN
  и перезапусти workflow «Build TogetherForever APK».

DONE
