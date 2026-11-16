"""Compare every imported value without printing accounts, hashes, or personal data."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.models.database import build_db_url
from scripts.import_sqlite import TABLES
from scripts.init_database import quote


def canonical(rows):
    return json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


async def verify(source):
    source=Path(source).resolve(strict=True)
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as disk:
        memory=sqlite3.connect(':memory:')
        disk.backup(memory)
    memory.row_factory=sqlite3.Row
    connection=await asyncpg.connect(build_db_url(),timeout=10)
    results={}
    try:
        # One MVCC snapshot for all PostgreSQL tables.
        async with connection.transaction(isolation='repeatable_read',readonly=True):
            source_tables={r[0] for r in memory.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            unexpected=source_tables-set(TABLES)-{'sqlite_sequence'}
            if unexpected:
                raise ValueError('SQLite contains unmapped tables; explicit migration review is required.')
            for table in TABLES:
                if table not in source_tables:
                    raise ValueError('SQLite is missing an expected project table.')
                source_rows=[dict(row) for row in memory.execute(f'SELECT * FROM {quote(table)} ORDER BY id')]
                columns={r['column_name']:r['data_type'] for r in await connection.fetch(
                    "SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=$1",table)}
                names=[r['name'] for r in memory.execute(f'PRAGMA table_info({quote(table)})')]
                selected=','.join(quote(name) for name in names)
                target_rows=[dict(row) for row in await connection.fetch(f'SELECT {selected} FROM {quote(table)} ORDER BY id')]
                for rows in (source_rows,target_rows):
                    for row in rows:
                        for name,value in row.items():
                            if value is not None and columns[name]=='boolean':row[name]=bool(value)
                            elif value is not None and columns[name] in ('json','jsonb'):row[name]=json.loads(value)
                matched=hashlib.sha256(canonical(source_rows).encode()).digest()==hashlib.sha256(canonical(target_rows).encode()).digest()
                results[table]={'sqlite_rows':len(source_rows),'postgres_rows':len(target_rows),'all_values_match':matched}
        print(json.dumps(results,indent=2))
        if not all(row['all_values_match'] for row in results.values()):
            raise ValueError('Imported values differ; do not cut over.')
        return results
    finally:
        await connection.close()
        memory.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sqlite',required=True)
    try:
        asyncio.run(verify(parser.parse_args().sqlite))
    except Exception as exc:
        sys.exit(f'Data verification failed ({type(exc).__name__}); cutover is not safe. No row contents printed.')
