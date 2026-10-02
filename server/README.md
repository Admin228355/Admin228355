# Свой сервер TogetherForever

Весь сервер поднимается одной командой: PocketBase (аккаунты, файлы, правила
доступа), hotpath на Postgres (чат, воспоминания, пары — быстрый путь),
Centrifugo (реальное время) и Caddy (HTTPS-сертификат выпускается сам).

Требования: Linux-сервер (Ubuntu 22.04/24.04), 1–2 ГБ памяти, домен,
открытые порты 80 и 443. Нет домена или нельзя открыть порты (домашний
компьютер, провайдер за NAT) — см. [«Туннель»](#туннель-без-домена-и-без-открытых-портов).

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
   git clone -b claude/gifted-cerf-hka1zf https://github.com/Admin228355/Admin228355 togetherforever
   cd togetherforever/server
   sudo ./install.sh togetherforever-ivan.duckdns.org твоя@почта.ru
   ```
   Первая сборка образов идёт 5–10 минут. В конце скрипт напечатает адрес
   админки и пароль администратора (он же лежит в `server/.env`).
6. **Приложение.** В репозитории на GitHub: *Settings → Secrets and variables →
   Actions → Variables → New repository variable*: `PB_URL` =
   `https://togetherforever-ivan.duckdns.org`. Затем *Actions → Build
   TogetherForever APK → Run workflow*. Через ~15 минут APK появится в Releases.

## Туннель: без домена и без открытых портов

Подходит для домашнего компьютера, ноутбука или мини-ПК с Linux и Docker (на
Windows — через WSL2 с Ubuntu). Белый IP и проброс портов на роутере не нужны:
туннель сам подключается к интернету и выставляет сервер наружу по HTTPS.
Сервер при этом живёт, пока включён компьютер.

Установка в этом режиме отличается одним флагом:

```bash
sudo ./install.sh --tunnel <публичный-адрес> <твоя@почта.ru> [токен-cloudflare]
```
Caddy слушает только `http://127.0.0.1:8080`, сертификаты не выпускает, порты
не открывает; HTTPS даёт туннель. Какой туннель выбрать:

### A. Tailscale Funnel — постоянный адрес, домен не нужен
1. Установи Tailscale и войди в аккаунт:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```
2. В [админке Tailscale](https://login.tailscale.com/admin/dns) включи *HTTPS
   Certificates*. Если Funnel не включён, команда из шага 5 напечатает ссылку,
   по которой его нужно разрешить.
3. Узнай свой адрес — он выглядит как `имя.tailnet-xxxx.ts.net`:
   ```bash
   tailscale status --json | python3 -c "import json,sys; print(json.load(sys.stdin)['Self']['DNSName'].rstrip('.'))"
   ```
4. Поставь сервер с этим адресом:
   ```bash
   sudo ./install.sh --tunnel имя.tailnet-xxxx.ts.net твоя@почта.ru
   ```
5. Открой его наружу: `sudo tailscale funnel --bg 8080`.
6. `PB_URL` в GitHub = `https://имя.tailnet-xxxx.ts.net`, затем запусти сборку APK.

### B. Cloudflare Tunnel — постоянный адрес, нужен свой домен
1. Бесплатный аккаунт на cloudflare.com и домен, добавленный в Cloudflare.
2. В панели *Zero Trust* → раздел *Tunnels* → *Create a tunnel* → *Cloudflared*.
   Скопируй токен (длинная строка, начинается с `eyJ`).
3. В туннеле добавь *Public hostname*, например `love.example.com`; сервис —
   `HTTP`, адрес `localhost:80`.
4. Поставь сервер, передав токен последним аргументом — контейнер `cloudflared`
   запустится вместе с остальными:
   ```bash
   sudo ./install.sh --tunnel love.example.com твоя@почта.ru ТОКЕН
   ```
5. `PB_URL` в GitHub = `https://love.example.com`, затем запусти сборку APK.

По условиям Cloudflare на бесплатном тарифе один запрос не может быть больше
100 МБ, поэтому очень тяжёлые видео через такой туннель не загрузятся.

### C. Быстрый туннель (`trycloudflare.com`) — только чтобы проверить
```bash
cloudflared tunnel --url http://localhost:8080
```
Команда напечатает адрес вида `https://что-то.trycloudflare.com`. Для жизни он
не годится: адрес случайный и **меняется при каждом запуске**, а он зашит в
APK при сборке; Server-Sent Events не поддерживаются, запросов одновременно не
больше 200, гарантий работы нет. Зато для проверки хватает: поставь сервер с
любым именем (`sudo ./install.sh --tunnel test.example.com почта`), запусти
команду выше и открой `https://что-то.trycloudflare.com/_/` — должна открыться
админка. Если адрес сменился, а сервер остаётся:

```bash
./set-domain.sh новый-адрес
```
Скрипт обновит адрес в настройках сервера (`.env`, Centrifugo, письма). Данные
он не трогает. `PB_URL` в GitHub придётся поменять и пересобрать APK.

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
