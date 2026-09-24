# Безопасность · Security

TogetherForever хранит приватные данные пар (воспоминания, фото, геопозицию).
Нашёл уязвимость — **сообщи приватно**, не публичным issue:
GitHub → вкладка **Security** → **Report a vulnerability**.

Опиши, что нашёл, как воспроизвести и чем это грозит. Не трогай чужие данные
во время проверки.

В репозитории нет секретов: ключи подписи, пароли и токены сервера живут
только в секретах CI и в `server/.env` на самом сервере (он в `.gitignore`).

---

Found a vulnerability? Please report it privately via GitHub → **Security** →
**Report a vulnerability**. No secrets are committed to this repository.
