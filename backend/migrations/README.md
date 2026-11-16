# Versioned PostgreSQL upgrades

Run from the repository root:

```sh
.venv/bin/python backend/scripts/init_database.py --check
.venv/bin/python backend/scripts/init_database.py
```

Default mode synchronizes additive model changes: new tables, nullable/defaulted
columns, indexes and constraints. Existing rows are preserved. Applying NOT NULL
without a default to a populated table, type changes, renames, removals and changed
constraints/indexes require an explicit reviewed migration. No reset/drop mode is
provided. Nullable relaxation and database-default changes are supported.

For unsafe/data-changing upgrades, add monotonically ordered SQL files such as
`0001_backfill_example.sql` here. Back up first. Scripts run exactly once before
schema synchronization inside the same transaction, recorded with a SHA-256
checksum in `creator_schema_migrations`. Do not edit applied files; add a new one.
An older checkout missing an applied migration is rejected. Use schema-qualified
identifiers if needed; the application uses `public` in a dedicated database.
Do not include transaction-control statements or CREATE INDEX CONCURRENTLY.
Explicit SQL is trusted, reviewed project code: it can be destructive. Automatic
synchronization itself never drops columns/tables, guesses renames or changes types.

Example for a required new column on a populated table:

```sql
ALTER TABLE "example" ADD COLUMN "label" VARCHAR(255);
UPDATE "example" SET "label" = 'legacy' WHERE "label" IS NULL;
ALTER TABLE "example" ALTER COLUMN "label" SET NOT NULL;
```

`--check` reports pending scripts without executing them and rolls back all scratch
DDL/bookkeeping. It requires schema-create permission for a temporary transactional
model-schema comparison. Synchronization uses an advisory lock and transactional
DDL. Runtime app startup does not perform DDL. Stop local app writes before updates;
review SQL and take a verified backup before running against a shared database.
