# Creator SN Backend

FastAPI + Tortoise ORM + PostgreSQL。包含 JWT/邀请注册、用户/成员/项目/产品管理。

完整配置见 [本地开发](../docs/development.md)。设置受保护配置中的 database_url，
或环境变量 DATABASE_URL，不再支持运行时 SQLite 回退。

从仓库根目录：

```sh
.venv/bin/python backend/scripts/init_database.py --check
.venv/bin/python backend/scripts/init_database.py
.venv/bin/python scripts/dev.py
```

只运行后端时必须以 backend 为工作目录，先同步结构：

```sh
cd backend
../.venv/bin/python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

- 表结构以 api/models/db_models.py 为准；安全增量同步及版本化 SQL 升级见 [迁移规则](migrations/README.md)。
- 应用禁用自动 generate_schemas，发布流程应在启动应用前显式执行同步脚本。
- 月度备份使用 pg_dump；需要可用且版本不低于服务端的 PostgreSQL 客户端。
- 本地旧 SQLite 可使用 scripts/import_sqlite.py 一次性导入空目标库，源文件保留。
