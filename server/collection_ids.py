#!/usr/bin/env python3
"""Печатает CID_<КОЛЛЕКЦИЯ>=<id> для hotpath.

hotpath отвечает в формате PocketBase, и в каждом ответе есть collectionId —
он обязан совпадать с id коллекций ЭТОГО сервера (у автора они свои).

    PB_URL=... PB_EMAIL=... PB_PASSWORD=... python3 server/collection_ids.py >> .env
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bootstrap import api, must, PB_EMAIL, PB_PASSWORD  # noqa: E402
from hotpath_schema import hot_collections  # noqa: E402

st, d = api('POST', '/api/collections/_superusers/auth-with-password',
            body={'identity': PB_EMAIL, 'password': PB_PASSWORD})
if st != 200:
    sys.exit(f'auth failed: {st} {d}')
token = d['token']
for name in hot_collections():
    st, col = api('GET', f'/api/collections/{name}', token)
    if st != 200:
        sys.exit(f'{name}: {st} {col}')
    print(f'CID_{name.upper()}={col["id"]}')
