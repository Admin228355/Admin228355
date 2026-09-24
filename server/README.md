# Свой сервер TogetherForever

Весь сервер поднимается одной командой: PocketBase (аккаунты, файлы, правила
доступа), hotpath на Postgres (чат, воспоминания, пары — быстрый путь),
Centrifugo (реальное время) и Caddy (HTTPS-сертификат выпускается сам).

Требования: Linux-сервер (Ubuntu 22.04/24.04), 1–2 ГБ памяти, домен,
открытые порты 80 и 443.

## Бесплатно: Oracle Cloud Always Free + DuckDNS

Oracle бесплатно и бессрочно даёт ARM-сервер (до 4 ядер и 24 ГБ памяти).
При регистрации нужна банковская карта: с неё не списывают деньги, она нужна
только для проверки.

1. **Домен.** Зайди на [duckdns.org](https://www.duckdns.org), войди через
   GitHub или Google и создай поддомен, например `togetherforever-ivan`.
   Получится `togetherforever-ivan.duckdns.org`.
2. **Сервер.** Зарегистрируйся на [oracle.com/cloud/free](https://www.oracle.com/cloud/free/)
   → *Create a VM instance*:
   - Image: **Ubuntu 24.04**, Shape: **VM.Standard.A1.Flex** (Ampere, 2 OCPU / 12 GB — бесплатно);
   - сохрани SSH-ключ, который предложит мастер.
3. **Порты.** *Networking → Virtual cloud networks → твоя сеть → Security Lists →
   Default → Add Ingress Rules*: источник `0.0.0.0/0`, TCP, порты `80,443`.
4. **IP в DuckDNS.** Скопируй публичный IP сервера и вставь его в поле *current ip*
   рядом со своим поддоменом на duckdns.org → *update ip*.
5. **Установка.** Подключись к серверу по SSH и выполни:
   ```bash
   git clone -b claude/affectionate-babbage-seyjvn https://github.com/Admin228355/Admin228355 togetherforever
   cd togetherforever/server
   sudo ./install.sh togetherforever-ivan.duckdns.org твоя@почта.ru
   ```
   Первая сборка образов идёт 5–10 минут. В конце скрипт напечатает адрес
   админки и пароль администратора (он же лежит в `server/.env`).
6. **Приложение.** В репозитории на GitHub: *Settings → Secrets and variables →
   Actions → Variables → New repository variable*: `PB_URL` =
   `https://togetherforever-ivan.duckdns.org`. Затем *Actions → Build
   TogetherForever APK → Run workflow*. Через ~15 минут APK появится в Releases.

## Другие варианты
- **Любой VPS** (от ~150–300 ₽/мес): те же шаги 5–6, домен — DuckDNS или свой.
- **Домашний компьютер** с Linux: DuckDNS + проброс портов 80 и 443 на роутере.
  Работает, пока компьютер включён.

## Обслуживание
```bash
cd togetherforever/server
docker compose ps                 # что запущено
docker compose logs -f hotpath    # логи сервиса
git pull && docker compose up -d --build   # обновление
```
Данные лежат в `server/data/` (база PocketBase, Postgres, сертификаты).
Бэкап — копия этой папки при остановленном сервере (`docker compose stop`).

## Что внутри
| Сервис | Зачем |
|---|---|
| `pocketbase` | аккаунты, файлы, правила доступа, серверные хуки (`pocketbase/pb_hooks`) |
| `hotpath` | горячие коллекции поверх Postgres (`pocketbase/hotpath`) |
| `postgres` | база hotpath |
| `centrifugo` | WebSocket реального времени (`/connection/websocket`) |
| `caddy` | HTTPS и маршрутизация (`Caddyfile`) |

Скрипты:
- `bootstrap.py` разворачивает схему PocketBase (идемпотентно);
- `hotpath_schema.py` генерирует SQL-схему Postgres из карты колонок hotpath;
- `collection_ids.py` выдаёт hotpath идентификаторы коллекций.

Все пользователи этого сервера получают Plus-возможности бесплатно
(`pocketbase/pb_hooks/free_edition.pb.js`).

### Необязательно
- **Письма** (сброс пароля): админка → *Settings → Mail settings* → SMTP
  (подойдёт почтовый ящик с паролем приложения).
- **TURN** для голоса в совместном просмотре за строгими NAT: задай
  `TURN_HOST`, `TURN_USER`, `TURN_PASS` для сервиса `pocketbase`.
