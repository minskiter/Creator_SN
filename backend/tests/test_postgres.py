"""Integration tests against disposable databases in the project-local cluster.

Run: .venv/bin/python -m unittest discover -s backend/tests -v
The tests never use the configured application/remote database.
"""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sqlite3
import sys
import tempfile
import unittest
from urllib.parse import quote
import uuid

import asyncpg

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from api.models import db_backup


class SQLNormalizationTests(unittest.TestCase):
    def test_string_defaults_are_not_rewritten(self):
        from scripts.init_database import normalized
        self.assertEqual(normalized("'public.example'::text",'public'),"'public.example'::text")
        self.assertEqual(normalized("nextval('public.user_id_seq'::regclass)",'public'),"nextval('user_id_seq'::regclass)")
        self.assertEqual(normalized('FOREIGN KEY (id) REFERENCES public.other(id)','public'),'FOREIGN KEY (id) REFERENCES other(id)')


class PostgreSQLTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        password_file = ROOT / '.local/postgres-admin-password'
        if not password_file.exists():
            self.skipTest('Start the isolated local PostgreSQL cluster first.')
        asyncio.get_running_loop().slow_callback_duration = 2
        self.admin = await asyncpg.connect(host='127.0.0.1', port=55432, user='creator_admin',
                                          password=password_file.read_text().strip(), database='postgres')
        self.name = 'creatorsn_test_' + uuid.uuid4().hex
        await self.admin.execute(f'CREATE DATABASE "{self.name}" OWNER creatorsn')
        password=(ROOT / '.local/postgres-app-password').read_text().strip()
        self.url=f'postgres://creatorsn:{quote(password,safe="")}@127.0.0.1:55432/{self.name}'
        self.env={**os.environ, 'DATABASE_URL':self.url}
        self.conn=await asyncpg.connect(self.url)
        result=self.sync()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    async def asyncTearDown(self):
        if hasattr(self,'conn'):
            await self.conn.close()
        if hasattr(self,'name'):
            await self.admin.execute(f'DROP DATABASE "{self.name}" WITH (FORCE)')
        if hasattr(self,'admin'):
            await self.admin.close()

    def sync(self, check=False):
        return subprocess.run([sys.executable,str(ROOT/'backend/scripts/init_database.py')]+(['--check'] if check else []),
                              cwd=ROOT, env=self.env, capture_output=True,text=True,timeout=30)

    async def add_user(self):
        await self.conn.execute("INSERT INTO userdbmodel(userid,pwd,name) VALUES('test-user','not-a-real-password','Keep me')")

    async def column_exists(self,name):
        return await self.conn.fetchval("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='userdbmodel' AND column_name=$1)",name)

    async def test_initialization_is_idempotent_and_records_version(self):
        self.assertEqual(self.sync().returncode,0)
        self.assertEqual(self.sync(check=True).returncode,0)
        self.assertEqual(await self.conn.fetchval('SELECT count(*) FROM creator_schema_migrations'),1)
        self.assertFalse(await self.conn.fetchval("SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname LIKE '_creatorsn_schema_%')"))

    async def test_check_is_read_only_and_nullable_column_is_repaired(self):
        await self.add_user()
        await self.conn.execute('ALTER TABLE userdbmodel DROP COLUMN email')
        self.assertEqual(self.sync(check=True).returncode,1)
        self.assertFalse(await self.column_exists('email'))
        result=self.sync()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue(await self.column_exists('email'))
        self.assertEqual(await self.conn.fetchval('SELECT name FROM userdbmodel'),'Keep me')
        self.assertEqual(self.sync(check=True).returncode,0)

    async def test_missing_table_is_created(self):
        await self.add_user()
        await self.conn.execute('DROP TABLE productreviewdbmodel')
        self.assertEqual(self.sync().returncode,0)
        self.assertIsNotNone(await self.conn.fetchval("SELECT to_regclass('public.productreviewdbmodel')"))
        self.assertEqual(await self.conn.fetchval('SELECT count(*) FROM userdbmodel'),1)

    async def test_required_column_on_populated_table_is_refused(self):
        await self.add_user()
        await self.conn.execute('ALTER TABLE userdbmodel DROP COLUMN pwd')
        result=self.sync()
        self.assertEqual(result.returncode,2,result.stdout+result.stderr)
        self.assertFalse(await self.column_exists('pwd'))
        self.assertEqual(await self.conn.fetchval('SELECT count(*) FROM userdbmodel'),1)

    async def test_unsafe_type_change_rolls_back_safe_changes(self):
        await self.add_user()
        await self.conn.execute('ALTER TABLE userdbmodel DROP COLUMN email; ALTER TABLE userdbmodel ALTER COLUMN name TYPE TEXT')
        self.assertEqual(self.sync().returncode,2)
        self.assertFalse(await self.column_exists('email'))
        self.assertEqual(await self.conn.fetchval('SELECT name FROM userdbmodel'),'Keep me')

    async def test_missing_unique_constraint_is_repaired(self):
        name=await self.conn.fetchval("SELECT conname FROM pg_constraint WHERE conrelid='userdbmodel'::regclass AND contype='u'")
        await self.conn.execute('ALTER TABLE userdbmodel DROP CONSTRAINT "'+name+'"')
        result=self.sync()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        await self.add_user()
        with self.assertRaises(asyncpg.UniqueViolationError):
            await self.add_user()

    async def test_missing_foreign_key_is_repaired(self):
        name=await self.conn.fetchval("SELECT conname FROM pg_constraint WHERE conrelid='productreviewdbmodel'::regclass AND contype='f'")
        await self.conn.execute('ALTER TABLE productreviewdbmodel DROP CONSTRAINT "'+name+'"')
        result=self.sync()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        count=await self.conn.fetchval("SELECT count(*) FROM pg_constraint WHERE conrelid='productreviewdbmodel'::regclass AND contype='f'")
        self.assertEqual(count,1)

    async def test_missing_index_is_planned_and_created(self):
        from scripts.init_database import plan_changes, snapshot
        await self.conn.execute('CREATE INDEX test_user_name ON userdbmodel (name)')
        expected=await snapshot(self.conn,'public')
        await self.conn.execute('DROP INDEX test_user_name')
        before,after,errors=await plan_changes(self.conn,expected,await snapshot(self.conn,'public'))
        self.assertFalse(before)
        self.assertFalse(errors)
        self.assertEqual(len(after),1)
        await self.conn.execute(after[0])
        self.assertIsNotNone(await self.conn.fetchval("SELECT to_regclass('public.test_user_name')"))

    async def test_sqlite_import_preserves_data_and_refuses_nonempty_target(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.local') as temp:
            source=Path(temp)/'source.sqlite3'
            with sqlite3.connect(source) as disk:
                disk.executescript("CREATE TABLE userdbmodel(id INTEGER PRIMARY KEY, userid TEXT, pwd TEXT); INSERT INTO userdbmodel VALUES(7,'import-user','not-a-real-password'); CREATE TABLE resumedbmodel(id TEXT PRIMARY KEY, introduction TEXT); INSERT INTO resumedbmodel VALUES('resume','{\"test\":true}'); CREATE TABLE projectdbmodel(id TEXT PRIMARY KEY, name TEXT, favor INTEGER); INSERT INTO projectdbmodel VALUES('project','Imported project',1);")
            digest=source.read_bytes()
            command=[sys.executable,str(ROOT/'backend/scripts/import_sqlite.py'),'--sqlite',str(source)]
            result=subprocess.run(command,cwd=ROOT,env=self.env,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(source.read_bytes(),digest)
            self.assertEqual(await self.conn.fetchval('SELECT id FROM userdbmodel'),7)
            self.assertIs(await self.conn.fetchval('SELECT favor FROM projectdbmodel'),True)
            self.assertEqual(json.loads(await self.conn.fetchval('SELECT introduction FROM resumedbmodel')),{'test':True})
            await self.conn.execute("INSERT INTO userdbmodel(userid,pwd) VALUES('next-user','not-a-real-password')")
            self.assertEqual(await self.conn.fetchval("SELECT id FROM userdbmodel WHERE userid='next-user'"),8)
            result=subprocess.run(command,cwd=ROOT,env=self.env,capture_output=True,text=True,timeout=30)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(await self.conn.fetchval('SELECT count(*) FROM userdbmodel'),2)

    async def test_changed_migration_checksum_is_refused(self):
        await self.conn.execute("UPDATE creator_schema_migrations SET checksum='tampered'")
        self.assertEqual(self.sync().returncode,2)

    async def test_defaulted_not_null_column_is_repaired(self):
        await self.conn.execute("INSERT INTO projectdbmodel(id,name,favor) VALUES('test','Keep project',false)")
        await self.conn.execute('ALTER TABLE projectdbmodel DROP COLUMN favor')
        result=self.sync()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIs(await self.conn.fetchval('SELECT favor FROM projectdbmodel'),False)

    async def test_versioned_backfill_runs_once_and_check_does_not_execute_it(self):
        await self.add_user()
        await self.conn.execute('ALTER TABLE userdbmodel ALTER COLUMN name TYPE TEXT')
        with tempfile.TemporaryDirectory(dir=ROOT/'.local') as temp:
            directory=Path(temp)
            (directory/'0001_initial.sql').write_text((ROOT/'backend/migrations/0001_initial.sql').read_text())
            (directory/'0002_fix_name.sql').write_text("ALTER TABLE userdbmodel ALTER COLUMN name TYPE VARCHAR(255); UPDATE userdbmodel SET name='Migrated';")
            code=("import asyncio,sys; from pathlib import Path; "
                  "sys.path.insert(0,str(Path('backend').resolve())); "
                  "import scripts.init_database as m; "
                  "m.MIGRATIONS=Path(sys.argv[1]); "
                  "sys.exit(0 if asyncio.run(m.synchronize(check=len(sys.argv)>2)) else 1)")
            def run(check=False):
                return subprocess.run([sys.executable,'-c',code,temp]+(['check'] if check else []),
                                      cwd=ROOT,env=self.env,capture_output=True,text=True,timeout=30)
            self.assertEqual(run(check=True).returncode,1)
            self.assertEqual(await self.conn.fetchval('SELECT name FROM userdbmodel'),'Keep me')
            result=run()
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(await self.conn.fetchval('SELECT name FROM userdbmodel'),'Migrated')
            await self.conn.execute("UPDATE userdbmodel SET name='After migration'")
            self.assertEqual(run().returncode,0)
            self.assertEqual(await self.conn.fetchval('SELECT name FROM userdbmodel'),'After migration')
            self.assertEqual(await self.conn.fetchval('SELECT count(*) FROM creator_schema_migrations'),2)

    async def test_backup_can_be_restored(self):
        await self.add_user()
        with tempfile.TemporaryDirectory(dir=ROOT/'.local') as temp:
            old_dir=db_backup.BACKUP_DIR
            old_url=os.environ.get('DATABASE_URL')
            try:
                db_backup.BACKUP_DIR=Path(temp)
                os.environ['DATABASE_URL']=self.url
                target=await asyncio.to_thread(db_backup.create_monthly_db_backup,force=True)
                self.assertTrue((target/'database.dump').stat().st_size>0)
                self.assertEqual((target/'database.dump').stat().st_mode & 0o777,0o600)
                restore_db=self.name+'_restore'
                await self.admin.execute(f'CREATE DATABASE "{restore_db}" OWNER creatorsn')
                try:
                    restore_env={**os.environ,'PGHOST':'127.0.0.1','PGPORT':'55432','PGUSER':'creatorsn',
                                 'PGPASSWORD':(ROOT/'.local/postgres-app-password').read_text().strip(),'PGDATABASE':restore_db}
                    binary=str(Path(db_backup.pg_dump_binary()).with_name('pg_restore'))
                    result=subprocess.run([binary,'--no-owner','--no-acl','--exit-on-error','--dbname',restore_db,str(target/'database.dump')],
                                          env=restore_env,capture_output=True,timeout=30)
                    self.assertEqual(result.returncode,0,'Restore failed')
                    connection=await asyncpg.connect(self.url.rsplit('/',1)[0]+'/'+restore_db)
                    try:
                        self.assertEqual(await connection.fetchval('SELECT name FROM userdbmodel'),'Keep me')
                    finally:
                        await connection.close()
                finally:
                    await self.admin.execute(f'DROP DATABASE "{restore_db}" WITH (FORCE)')
            finally:
                db_backup.BACKUP_DIR=old_dir
                if old_url is None:os.environ.pop('DATABASE_URL',None)
                else:os.environ['DATABASE_URL']=old_url


if __name__=='__main__':
    unittest.main()
