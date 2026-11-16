"""One-time, transactional import from local SQLite into an EMPTY PostgreSQL schema."""
import argparse
import asyncio
import json
from pathlib import Path
import sqlite3
import sys

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.models.database import build_db_url
from scripts.init_database import LOCK_ID, quote

TABLES = ('userdbmodel', 'resumedbmodel', 'memberdbmodel', 'productdbmodel',
          'projectdbmodel', 'productattributedbmodel', 'productreviewdbmodel', 'productattributevaluedbmodel')


async def import_database(source):
    source = Path(source).resolve(strict=True)
    # Backup API takes a consistent read-only snapshot, including committed WAL data.
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as disk:
        memory = sqlite3.connect(':memory:')
        disk.backup(memory)
    memory.row_factory = sqlite3.Row
    connection = await asyncpg.connect(build_db_url(), timeout=10)
    try:
        async with connection.transaction():
            await connection.execute('SELECT pg_advisory_xact_lock($1)', LOCK_ID)
            # Prevent concurrent writes between the emptiness check and insertion.
            await connection.execute('LOCK TABLE ' + ','.join(quote(t) for t in TABLES) + ' IN EXCLUSIVE MODE')
            for table in TABLES:
                if await connection.fetchval(f'SELECT EXISTS(SELECT 1 FROM {quote(table)} LIMIT 1)'):
                    raise ValueError('Target must have no project rows; import before starting the app. Nothing was imported.')
            counts = {}
            existing = {row[0] for row in memory.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in TABLES:
                if table not in existing:
                    continue
                rows = memory.execute(f'SELECT * FROM {quote(table)}').fetchall()
                columns = {r['column_name']: r['data_type'] for r in await connection.fetch(
                    "SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=$1", table)}
                if rows:
                    names = list(rows[0].keys())
                    if set(names) - columns.keys():
                        raise ValueError(f'Source contains unsupported columns in {table}; review before import.')
                    values=[]
                    for row in rows:
                        value=[]
                        for name in names:
                            item=row[name]
                            if item is not None and columns[name]=='boolean':
                                if item not in (0,1):
                                    raise ValueError(f'Invalid boolean value in {table}.{name}')
                                item=bool(item)
                            elif item is not None and columns[name] in ('json','jsonb'):
                                item=json.dumps(json.loads(item))
                            value.append(item)
                        values.append(value)
                    statement=f'INSERT INTO {quote(table)} (' + ','.join(quote(n) for n in names) + ') VALUES (' + ','.join(f'${n+1}' for n in range(len(names))) + ')'
                    await connection.executemany(statement, values)
                counts[table]=len(rows)
                sequence=await connection.fetchval('SELECT pg_get_serial_sequence($1,$2)',table,'id')
                if sequence:
                    maximum=await connection.fetchval(f'SELECT MAX(id) FROM {quote(table)}')
                    await connection.fetchval('SELECT setval($1::regclass,$2,$3)',sequence,maximum or 1,maximum is not None)
            print(json.dumps({'imported_rows':counts,'source_preserved':True},indent=2))
    finally:
        await connection.close()
        memory.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sqlite',required=True,help='existing SQLite file (read-only; not deleted)')
    try:
        asyncio.run(import_database(parser.parse_args().sqlite))
    except Exception as exc:
        sys.exit(f'Import failed ({type(exc).__name__}); target must be empty and schema-compatible. Transaction rolled back; source retained.')
