#!/usr/bin/env python3
"""Разворачивает схему TogetherForever на пустом PocketBase.

Идемпотентно: можно запускать повторно, ничего не удаляет.

    PB_URL=http://127.0.0.1:8090 PB_EMAIL=admin@example.com PB_PASSWORD=... \\
        python3 server/bootstrap.py

Что делает:
  1. заводит все коллекции из pocketbase/collections_schema.json (сначала без
     правил доступа — они ссылаются на поле users.group_ids, которого ещё нет);
  2. дописывает в системную коллекцию users поля приложения и скрытое
     users.group_ids (его держит хук groups_membership.pb.js);
  3. заливает схему ещё раз, уже с правилами доступа;
  4. добавляет то, что у автора жило в отдельных скриптах и миграциях:
     groups.messages_count, canvas_catalogue.sheet_ratio, коллекцию love_tests.
"""
import copy
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(HERE, '..', 'pocketbase', 'collections_schema.json')

PB_URL = os.environ.get('PB_URL', 'http://127.0.0.1:8090').rstrip('/')
PB_EMAIL = os.environ['PB_EMAIL']
PB_PASSWORD = os.environ['PB_PASSWORD']

RULES = ('listRule', 'viewRule', 'createRule', 'updateRule', 'deleteRule')


def api(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(PB_URL + path, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', token)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {'raw': raw}


def must(step, st, d, ok=(200, 204)):
    if st not in ok:
        sys.exit(f'[{step}] HTTP {st}: {json.dumps(d, ensure_ascii=False)[:800]}')
    print(f'[{step}] ok')


def f_text(n):
    return {'name': n, 'type': 'text', 'required': False, 'max': 0}


def f_num(n):
    return {'name': n, 'type': 'number', 'required': False}


def f_bool(n):
    return {'name': n, 'type': 'bool', 'required': False}


def f_date(n):
    return {'name': n, 'type': 'date', 'required': False}


def f_json(n):
    return {'name': n, 'type': 'json', 'required': False, 'maxSize': 5000000}


# Поля users, с которыми работают приложение и хуки (у автора их заводили
# apply_schema.py, apply_draw_invite_fields.py и руками в админке).
USERS_FIELDS = [
    f_num('mute_until'), f_num('sunrise_until'), f_num('spa_until'),
    f_num('streak_shield_until'), f_num('secrets_until'),
    f_text('display_name'), f_text('avatar_url'), f_text('banner_url'),
    f_text('gender'), f_date('birth_date'), f_num('coins'),
    f_json('owned_themes'), f_json('owned_icons'), f_json('owned_features'),
    f_json('granted_badges'), f_text('badge'), f_text('pair_id'), f_json('pair_ids'),
    f_text('invite_code'), f_text('fcm_token'), f_json('fcm_tokens'),
    f_bool('notif_miss_you'), f_bool('notif_new_memory'), f_bool('notif_mood'),
    f_bool('notif_chat'), f_bool('notif_draw'), f_bool('notif_comments'),
    f_text('notif_synced_at'), f_json('solo_timers'),
    f_date('updated_at'), f_date('last_daily_bonus_at'), f_date('last_memory_reward_at'),
    f_text('ad_rewards_date'), f_num('ad_rewards_today'), f_bool('dev_coins_granted'),
    f_json('ad_grants'), f_text('ad_views_date'), f_num('ad_views_today'),
    f_text('task_rewards_date'), f_text('task_rewards_ids'),
    f_bool('partner_invite_reward_granted'), f_json('partner_invite_rewarded_keys'),
    f_json('mood_streak_rewards'), f_num('last_daily_bonus_ms'), f_num('last_memory_reward_ms'),
    f_bool('plus'), f_num('last_plus_grant_ms'), f_text('platform'), f_text('plus_platform'),
    f_json('mascot_sleep'), f_json('custom_themes'), f_json('miss_you_wishes'),
    f_num('theme_id'), f_text('theme_mode'), f_num('draw_invite_ms'),
    f_text('apns_token'), f_bool('apns_sandbox'), f_num('apns_bg_ms'),
    f_text('public_slug'), f_text('account_token'),
]

USERS_ID = {
    'name': 'id', 'type': 'text', 'primaryKey': True, 'required': True,
    'system': True, 'pattern': '^[A-Za-z0-9_-]+$', 'min': 1, 'max': 50,
    'autogeneratePattern': '[a-z0-9]{15}',
}


def member_authored(author):
    e = '@request.auth.id != "" && @request.auth.group_ids.id ?= group_id'
    r = {k: e for k in RULES}
    r['createRule'] = f'{e} && {author} = @request.auth.id'
    return r


def add_fields(token, name, fields):
    st, col = api('GET', f'/api/collections/{name}', token)
    must(f'get {name}', st, col, ok=(200,))
    have = {f['name'] for f in col['fields']}
    new = [f for f in fields if f['name'] not in have]
    if not new:
        print(f'[{name}] поля уже на месте')
        return col
    col['fields'] += new
    st, d = api('PATCH', f'/api/collections/{col["id"]}', token, col)
    must(f'{name} +{len(new)} полей', st, d, ok=(200,))
    return d


def main():
    st, d = api('POST', '/api/collections/_superusers/auth-with-password',
                body={'identity': PB_EMAIL, 'password': PB_PASSWORD})
    must('auth', st, d, ok=(200,))
    token = d['token']

    with open(SCHEMA, encoding='utf-8') as f:
        schema = json.load(f)
    # Экспорт автора без системных дат, а индексы и офлайн-синхронизация
    # клиента на них опираются (фильтр по `updated`).
    for c in schema['collections']:
        names = {f['name'] for f in c['fields']}
        for n, on_update in (('created', False), ('updated', True)):
            if n not in names:
                c['fields'].append({'name': n, 'type': 'autodate', 'system': False,
                                    'onCreate': True, 'onUpdate': on_update})

    bare = copy.deepcopy(schema)
    for c in bare['collections']:
        for k in RULES:
            c[k] = None
    st, d = api('PUT', '/api/collections/import', token, bare)
    must('коллекции (без правил)', st, d)

    st, groups = api('GET', '/api/collections/groups', token)
    must('get groups', st, groups, ok=(200,))

    st, users = api('GET', '/api/collections/users', token)
    must('get users', st, users, ok=(200,))
    users['fields'] = [USERS_ID if f['name'] == 'id' else f
                       for f in users['fields'] if f['name'] != 'firebase_uid']
    have = {f['name'] for f in users['fields']}
    users['fields'] += [f for f in USERS_FIELDS if f['name'] not in have]
    if 'group_ids' not in have:
        users['fields'].append({
            'name': 'group_ids', 'type': 'relation', 'required': False,
            'hidden': True, 'collectionId': groups['id'],
            'cascadeDelete': False, 'minSelect': 0, 'maxSelect': 999,
        })
    users['indexes'] = [s for s in users.get('indexes', [])
                        if 'idx_users_firebase_uid' not in s]
    st, d = api('PATCH', f'/api/collections/{users["id"]}', token, users)
    must('users: поля приложения + group_ids', st, d, ok=(200,))

    st, d = api('PUT', '/api/collections/import', token, schema)
    must('коллекции с правилами доступа', st, d)

    add_fields(token, 'groups', [f_num('messages_count')])
    add_fields(token, 'canvas_catalogue', [f_num('sheet_ratio')])

    # Горячие коллекции живут в Postgres (hotpath), но SQLite остаётся
    # зеркалом (группы, присутствие) и источником правил доступа — колонки
    # должны совпадать с картой hotpath, иначе зеркало падает на записи.
    sys.path.insert(0, HERE)
    from hotpath_schema import hot_collections
    kinds = {'text': f_text, 'date': f_text, 'num': f_num, 'bool': f_bool,
             'json': f_json, 'jsontext': f_json}
    for name, columns in hot_collections().items():
        add_fields(token, name, [kinds[t](c) for c, t in columns.items()
                                 if t in kinds])

    st, _ = api('GET', '/api/collections/love_tests', token)
    if st == 404:
        body = {
            'name': 'love_tests', 'type': 'base',
            'fields': [f_text('group_id'), f_text('user_uid'),
                       f_json('data'), f_num('total'),
                       {'name': 'created', 'type': 'autodate', 'onCreate': True, 'onUpdate': False},
                       {'name': 'updated', 'type': 'autodate', 'onCreate': True, 'onUpdate': True}],
            'indexes': ['CREATE INDEX idx_love_tests_group ON love_tests (group_id)'],
            **member_authored('user_uid'),
        }
        st, d = api('POST', '/api/collections', token, body)
        must('love_tests', st, d, ok=(200,))
    else:
        print('[love_tests] уже есть')

    # Имя и адрес сервера — в письмах сброса пароля и в админке.
    app_url = os.environ.get('APP_URL', '').rstrip('/')
    if app_url:
        st, d = api('PATCH', '/api/settings', token, {
            'meta': {'appName': 'TogetherForever', 'appURL': app_url}})
        must('настройки сервера', st, d, ok=(200,))

    print('Готово: схема TogetherForever развёрнута.')


if __name__ == '__main__':
    main()
