<div align="center">

<img src="docs/branding/app-icon-512.png" alt="TogetherForever" width="120">

# TogetherForever

**Уютное приватное пространство для двоих — бесплатно, без рекламы и подписок.**

Общие воспоминания · настроения · чат · совместное рисование · карта «Где мы» · виджеты на рабочий стол

[![License](https://img.shields.io/badge/license-GPL--3.0-E75480?style=for-the-badge)](LICENSE)
![Flutter](https://img.shields.io/badge/Flutter-02569B?style=for-the-badge&logo=flutter&logoColor=white)
![Android](https://img.shields.io/badge/Android-3DDC84?style=for-the-badge&logo=android&logoColor=white)

[**⬇ Скачать APK**](../../releases/latest) · [Свой сервер](server/README.md) · [English](#english)

</div>

---

## Что это

TogetherForever — свободный форк приложения [Togetherly](https://github.com/THET1ME-1/Togetherly)
(GPL-3.0). В оригинале часть возможностей платная и есть реклама. Здесь всё открыто для всех,
а данные хранятся на **своём** сервере, который ставится одной командой.

### Что внутри
- 📸 **Лента воспоминаний**: фото, видео, места, музыка, книги и фильмы
- 💌 **Капсула времени**: письмо откроется в выбранный день
- 🔒 **Секретные воспоминания** под PIN-кодом
- 💬 **Чат** с голосовыми сообщениями и видео-кружочками любой формы
- 🎨 **Совместное рисование**, раскраски вдвоём, открытки
- 😊 **Настроения** и история настроения партнёра
- 🗺️ **Карта «Где мы»** в реальном времени
- 🧩 **Виджеты** на рабочий стол: фото дня, дни вместе, серия, настроение
- 🌸 **Календарь цикла** с прогнозом
- 🐣 **Маскот пары**, который растёт вместе с вами
- 🎬 **Совместный просмотр** видео с голосовой связью
- 🏆 Достижения пары, «скучаю», таймеры, желания

### Чем отличается от оригинала
| | Togetherly | **TogetherForever** |
|---|---|---|
| Togetherly+ (цикл, новые виджеты, свои темы, кружочки любой формы) | платно | **бесплатно** |
| Темы, фоны холста, значки, маскоты, паки настроений за монеты | за монеты | **открыты все** |
| Реклама (баннеры, ролики, межстраничная) | есть | **нет** |
| Цветовые темы | 25 | **35** + своя тема из любого цвета или фото |
| Сервер | сервер автора | **свой** (`server/`, одна команда) |

## Как пользоваться

1. **Сервер.** Нужен один на всех, кто будет пользоваться твоей сборкой. Инструкция:
   [server/README.md](server/README.md) — бесплатный вариант на Oracle Cloud Always Free
   или [свой компьютер за туннелем](server/README.md#туннель-без-домена-и-без-открытых-портов)
   (Tailscale Funnel / Cloudflare Tunnel, без домена и открытых портов).
2. **Сборка приложения.** В репозитории: *Settings → Secrets and variables → Actions → Variables*
   → `PB_URL = https://твой-домен`. GitHub Actions сам соберёт APK и выложит его в
   [Releases](../../releases/latest).
3. **Установка.** На телефоне скачай `TogetherForever-…-arm64-v8a.apk` и открой.
   Зарегистрируйся по почте, пригласи партнёра кодом или QR.

> Для автообновлений подойдёт [Obtainium](https://github.com/ImranR98/Obtainium):
> *Add App* → ссылка на этот репозиторий.

### Постоянная подпись APK (по желанию)
Без неё каждая сборка подписывается новым отладочным ключом, и обновить приложение поверх
старого не выйдет — придётся переустанавливать. Чтобы обновлялось поверх:

```bash
keytool -genkey -v -keystore tf.jks -keyalg RSA -keysize 2048 -validity 10000 -alias tf
base64 -w0 tf.jks   # вывод — в секрет KEYSTORE_BASE64
```
Секреты репозитория: `KEYSTORE_BASE64`, `KEYSTORE_PASSWORD`, `KEY_ALIAS` (= `tf`), `KEY_PASSWORD`.

## Ограничения
- **Вход через Google и пуши Firebase** не работают: для них нужны ключи Google, выпущенные
  именно под этот проект. Вход по почте работает, уведомления приходят через фоновый канал
  приложения.
- iOS-сборки нет: для неё нужен аккаунт Apple Developer.

## Для разработчиков
```bash
flutter pub get
flutter run --dart-define=PB_URL=https://твой-домен
```
- `lib/` — приложение (Flutter, Material 3)
- `lib/config/brand.dart` — название, адрес сервера, ссылки
- `lib/config/free_edition.dart` — флаг «всё бесплатно, без рекламы»
- `server/` — сервер одной командой (PocketBase + hotpath/Postgres + Centrifugo + Caddy)
- `tool/brand/` — генераторы иконок и страниц сервера

## Лицензия
[GPL-3.0](LICENSE). Основано на [Togetherly](https://github.com/THET1ME-1/Togetherly) — спасибо
автору оригинала. Название и иконка TogetherForever не связаны с брендом Togetherly.

---

## English

**TogetherForever** is a free, ad-free fork of [Togetherly](https://github.com/THET1ME-1/Togetherly)
(GPL-3.0), a private space for couples: shared memories, moods, chat, drawing together, a live map,
home-screen widgets and more. Everything that was paid in the original (Togetherly+ and coin items)
is unlocked, ads are removed, and there are 10 new colour themes.

It runs on **your own server**: `server/install.sh` deploys the whole backend (PocketBase, hotpath +
Postgres, Centrifugo, Caddy with automatic HTTPS) with one command. Set the repository variable
`PB_URL` and GitHub Actions builds the APK and publishes it to Releases.
