#!/usr/bin/env python3
"""SQL-схема Postgres для hotpath.

У автора таблицы горячих коллекций создавались переносом из боевой базы
(hotpath/migrate_*.py), отдельного DDL для них в репозитории нет. Здесь он
собирается из той же карты колонок, по которой работает сам hotpath
(COLLECTIONS в pocketbase/hotpath/hotpath.py), по правилам уже существующих
таблиц (hotpath/groups_table.sql): text NOT NULL DEFAULT '', числа — double
precision, json — jsonb, даты и `updated` — text в формате PocketBase.

    python3 server/hotpath_schema.py > schema.sql
"""
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOTPATH = ROOT / 'pocketbase' / 'hotpath'

TYPES = {
    'text': "text NOT NULL DEFAULT ''",
    'date': "text NOT NULL DEFAULT ''",
    'auto': "text NOT NULL DEFAULT ''",
    'num': 'double precision NOT NULL DEFAULT 0',
    'bool': 'boolean NOT NULL DEFAULT false',
    'json': 'jsonb',
    'jsontext': 'jsonb',  # json в базе, строка в ответе
}

# Таблицы, чей DDL автор написал руками: их берём как есть и лишь добиваем
# недостающими колонками.
CURATED_FIRST = ['groups_table.sql', 'miss_you_table.sql']
CURATED_AFTER = ['note_fields.sql', 'chat_background.sql',
                 'canvas_meta_outline.sql', 'movies_cache.sql']


def hot_collections():
    tree = ast.parse((HOTPATH / 'hotpath.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and getattr(node.targets[0], 'id', None) == 'COLLECTIONS'):
            out = {}
            for k, v in zip(node.value.keys, node.value.values):
                cols = {}
                for kk, vv in zip(v.keys, v.values):
                    if getattr(kk, 'value', None) == 'columns':
                        cols = {c.value: t.value for c, t in zip(vv.keys, vv.values)}
                out[k.value] = cols
            return out
    raise SystemExit('COLLECTIONS не найден в hotpath.py')


def pb_indexes():
    """Индексы коллекций из схемы PocketBase, переведённые на Postgres."""
    schema = json.loads((ROOT / 'pocketbase' / 'collections_schema.json')
                        .read_text(encoding='utf-8'))
    out = {}
    for c in schema['collections']:
        out[c['name']] = [re.sub(r'`', '"', s) for s in c.get('indexes', [])]
    return out


def main():
    cols = hot_collections()
    idx = pb_indexes()
    parts = ['-- Сгенерировано server/hotpath_schema.py. Идемпотентно.',
             'SET client_min_messages = warning;', 'BEGIN;']
    for f in CURATED_FIRST:
        parts.append((HOTPATH / f).read_text(encoding='utf-8'))
    for name, columns in cols.items():
        body = ['  id text PRIMARY KEY'] + [
            f'  "{c}" {TYPES[t]}' for c, t in columns.items() if c != 'id']
        parts.append(f'CREATE TABLE IF NOT EXISTS {name} (\n' + ',\n'.join(body) + '\n);')
        for c, t in columns.items():
            parts.append(f'ALTER TABLE {name} ADD COLUMN IF NOT EXISTS "{c}" {TYPES[t]};')
        for s in idx.get(name, []):
            # Индекс на колонку, которой в горячей таблице нет, пропускаем.
            inside = s[s.rfind('(') + 1:s.rfind(')')]
            names = {n.strip().strip('"').split()[0] for n in inside.split(',')}
            if names - set(columns) - {'id'}:
                continue
            s = re.sub(r'CREATE (UNIQUE )?INDEX ', r'CREATE \1INDEX IF NOT EXISTS ', s)
            parts.append(s.rstrip(';') + ';')
        if 'group_id' in columns and 'updated' in columns:
            parts.append(f'CREATE INDEX IF NOT EXISTS idx_hp_{name}_group_updated '
                         f'ON {name} (group_id, updated);')
    for f in CURATED_AFTER:
        parts.append((HOTPATH / f).read_text(encoding='utf-8'))
    parts.append('COMMIT;')
    print('\n\n'.join(parts))


if __name__ == '__main__':
    main()
