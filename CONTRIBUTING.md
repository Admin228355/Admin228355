# Как помочь проекту

1. Форкни репозиторий и сделай ветку.
2. `flutter pub get`, затем `flutter analyze lib` — новых ошибок быть не должно.
3. Запуск со своим сервером:
   ```bash
   flutter run --dart-define=PB_URL=https://твой-домен
   ```
4. Открой Pull Request с описанием, что и зачем поменял.

Сервер — в `server/` (см. `server/README.md`). Код приложения — `lib/`,
серверные хуки — `pocketbase/pb_hooks/`, горячие коллекции — `pocketbase/hotpath/`.

Проект — форк [Togetherly](https://github.com/THET1ME-1/Togetherly) под GPL-3.0:
любые изменения распространяются под той же лицензией.
