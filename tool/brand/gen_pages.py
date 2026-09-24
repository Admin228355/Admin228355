"""Страницы сервера TogetherForever (pocketbase/pb_public).

Главная, конфиденциальность, условия, удаление аккаунта. Адрес репозитория
стоит плейсхолдером __REPO_URL__ — его подставляет сборка образа
(server/Dockerfile.pocketbase, аргумент REPO_URL).

    python3 tool/brand/gen_pages.py
"""
import os
from pathlib import Path

PUB = Path(__file__).resolve().parents[2] / 'pocketbase' / 'pb_public'
REPO = '__REPO_URL__'

STYLE = """<style>
:root{--bg:#fff7f8;--card:#ffffff;--ink:#2a1a1f;--muted:#6f5a60;--accent:#c93d6a;--line:#f3d9e1}
@media (prefers-color-scheme:dark){:root{--bg:#1a1216;--card:#241a1f;--ink:#f6e9ee;--muted:#c2a9b2;--accent:#ff86a8;--line:#3a2a31}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:760px;margin:0 auto;padding:40px 16px 64px}
.card{background:var(--card);border:1px solid var(--line);border-radius:24px;padding:24px 20px;margin-top:20px}
h1{font-size:30px;line-height:1.2;margin:12px 0 4px}h2{font-size:20px;margin:24px 0 8px}
p,li{color:var(--muted)}a{color:var(--accent)}
.logo{width:72px;height:72px;border-radius:18px;display:block}
.btn{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;padding:12px 20px;border-radius:999px;font-weight:600;margin:8px 8px 0 0}
.btn.ghost{background:transparent;color:var(--accent);border:1.5px solid var(--accent)}
footer{margin-top:32px;font-size:14px;color:var(--muted)}
</style>"""

HEART = ('<svg class="logo" viewBox="0 0 72 72" aria-hidden="true">'
         '<rect width="72" height="72" rx="18" fill="#FDE3E2"/>'
         '<path d="M27 53C14 44 10 36 13 29c3-6 11-7 14-1 4-6 12-5 15 1 3 7-1 15-15 24z" fill="#E75480"/>'
         '<path d="M46 55c-12-8-15-15-13-21 2-6 9-7 13-2 4-5 11-4 13 2 2 6-1 13-13 21z" '
         'fill="none" stroke="#E75480" stroke-width="4"/></svg>')


def page(title, desc, body):
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><meta name="description" content="{desc}">
{STYLE}</head><body><main>
{HEART}
{body}
<footer>TogetherForever — свободный форк <a href="https://github.com/THET1ME-1/Togetherly">Togetherly</a> (GPL-3.0).<br>
<a href="/">Главная</a> · <a href="/privacy-policy">Конфиденциальность</a> · <a href="/terms">Условия</a> · <a href="/delete-account">Удаление аккаунта</a></footer>
</main></body></html>
"""


PAGES = {
    'index.html': page('TogetherForever — приложение для двоих',
        'TogetherForever — бесплатное приложение для пар без рекламы.', f"""
<h1>TogetherForever</h1>
<p>Уютное приватное пространство для двоих: общие воспоминания, настроения, чат, совместное рисование, карта «где мы», виджеты на рабочий стол и маленькие ритуалы, которые держат вас рядом. Бесплатно, без рекламы и подписок.</p>
<div class="card">
<h2>Как начать</h2>
<ol><li>Скачай APK (файл <b>arm64-v8a</b>) в разделе Releases.</li>
<li>Зарегистрируйся по почте и пригласи партнёра кодом или QR.</li>
<li>Всё открыто сразу: темы, виджеты, календарь, маскоты.</li></ol>
<a class="btn" href="{REPO}/releases/latest">Скачать APK</a>
<a class="btn ghost" href="{REPO}">Исходный код</a>
</div>"""),
    'privacy-policy/index.html': page('Конфиденциальность — TogetherForever',
        'Политика конфиденциальности TogetherForever.', """
<h1>Политика конфиденциальности</h1>
<div class="card">
<p>Этот сервер TogetherForever хранит только то, что нужно для работы приложения: почту и пароль (в виде хэша) для входа, профиль (имя, аватар), данные пары — воспоминания, фото, сообщения, настроения, рисунки, таймеры, — а также геопозицию, если ты сам включил карту «Где мы».</p>
<h2>Кто видит данные</h2>
<p>Твои записи видит только твоя пара или группа. Данные не продаются и не передаются рекламным сетям — рекламы в приложении нет.</p>
<h2>Где хранятся</h2>
<p>На сервере, адрес которого указан в строке браузера. Им управляет тот, кто его развернул.</p>
<h2>Календарь цикла</h2>
<p>Эти данные вносятся только с твоего согласия и видны тебе и тем, с кем ты сам ими поделился.</p>
<h2>Удаление</h2>
<p>Удалить аккаунт и все данные можно в приложении — см. <a href="/delete-account">удаление аккаунта</a>.</p>
</div>"""),
    'terms/index.html': page('Условия — TogetherForever',
        'Условия использования TogetherForever.', f"""
<h1>Условия использования</h1>
<div class="card">
<p>TogetherForever — свободное программное обеспечение (GPL-3.0), основанное на проекте Togetherly. Приложение и сервер предоставляются «как есть», без гарантий бесперебойной работы.</p>
<h2>Правила</h2>
<ul><li>Не публикуй чужие персональные данные без согласия.</li>
<li>Не загружай незаконный контент и контент, нарушающий чужие права.</li>
<li>Не пытайся получить доступ к чужим данным или нарушить работу сервера.</li></ul>
<p>Администратор сервера вправе удалить аккаунт, нарушающий эти правила.</p>
<h2>Исходный код</h2>
<p><a href="{REPO}">{REPO}</a></p>
</div>"""),
    'delete-account/index.html': page('Удаление аккаунта — TogetherForever',
        'Как удалить аккаунт TogetherForever.', f"""
<h1>Удаление аккаунта</h1>
<div class="card">
<p>Открой приложение → Профиль → Настройки → <b>Удалить аккаунт</b>. Аккаунт и связанные данные (профиль, воспоминания, сообщения, фото) удаляются с сервера.</p>
<p>Нет доступа к приложению — напиши в <a href="{REPO}/issues">Issues проекта</a>.</p>
</div>"""),
}


def main():
    for path, html in PAGES.items():
        full = PUB / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(html, encoding='utf-8')
    print('pages:', len(PAGES))


if __name__ == '__main__':
    main()
