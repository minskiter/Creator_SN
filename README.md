# Creator SN

Vue 3 / Vite / Fluent 组件库前端 + FastAPI / Tortoise ORM / PostgreSQL 后端。

- `ui/`：前端。
- `backend/`：API、模型、表结构升级及最终运行镜像。
- [本地开发环境](docs/development.md)：Node 22 + Python 3.13 + PostgreSQL，一键启动。
- [数据库升级规则](backend/migrations/README.md)：增量同步、版本化 SQL、事务回滚。

## 本地启动

```sh
brew install postgresql@18
./scripts/setup-dev.sh
.venv/bin/python scripts/dev.py
```

网站 http://127.0.0.1:8080，API 文档 http://127.0.0.1:8000/docs。
配置/密码不入库；SQLite 原文件保留，但运行时只使用 PostgreSQL。

## Docker（需显式配置，不会自动迁移线上 SQLite）

镜像内置前端构建，无独立前端容器；Web 端口仍是 `60081 → 8000`。
Compose 需要在受保护环境中设置 DATABASE_URL，指向容器可访问的 PostgreSQL
（容器内 127.0.0.1 不是宿主机）。数据库必须预先创建；不会自动运行 PostgreSQL 容器。

运行时只读挂载 backend/api/app_config.json，不把管理员密码/JWT 密钥打入镜像。
远程 Docker context 下，配置文件和 CREATOR_SN_DATA_DIR 必须是服务端路径。
可使用 CREATOR_SN_CONFIG_FILE 指定服务端配置文件的绝对路径。
数据目录仅用于上传、备份及保留旧数据；PostgreSQL 数据由数据库服务单独管理。

部署前应审阅差异、备份并停写，先检查/执行结构升级，再启动：

```sh
# 确保当前 Docker context 是你准备操作的目标；不要直接对生产运行这些命令。
docker compose build web
docker compose run --rm web python scripts/init_database.py --check
docker compose run --rm web python scripts/init_database.py
docker compose up -d web
```

`--check` 有待升级项时返回 1；这与连接/配置异常（退出 2）不同。
不提供自动删库/重置模式。生产 SQLite 转 PostgreSQL 必须另行制定并验证数据迁移方案，
本地切换不代表线上已迁移。pg_dump 客户端版本必须不低于 PostgreSQL 服务端版本。
