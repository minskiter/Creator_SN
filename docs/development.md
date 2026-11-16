# 本地开发环境（PostgreSQL）

已验证 macOS Apple Silicon、Node.js 22.17.1 / npm 10.9.2、Python 3.13.16、
PostgreSQL 18.6。前端沿用 package-lock，后端使用独立 .venv 和开发依赖锁文件。

## 安装与启动

```sh
cd /Users/minskiter/Desktop/workspace/Creator_SN
# 新机器先安装 PostgreSQL 服务端工具（不必启动全局 Homebrew service）
brew install postgresql@18
# 首次安装/重装
./scripts/setup-dev.sh
# 开发：启动前自动同步模型表结构；Ctrl+C 停止前后端
.venv/bin/python scripts/dev.py
```

如 Python 不在 PATH：`PYTHON=/opt/homebrew/bin/python3.13 ./scripts/setup-dev.sh`。
使用 Node 22（nvm 用户可执行 `nvm use`）。不需要 Docker。

- 前端：http://127.0.0.1:8080/
- 登录：http://127.0.0.1:8080/#/login
- 管理：http://127.0.0.1:8080/#/admin
- API 文档：http://127.0.0.1:8000/docs
- 数据库：127.0.0.1:55432 / creatorsn_dev（数据库角色 creatorsn，非超级用户）

数据库为本仓库独立的 `.local/postgres` 集群，SCRAM 密码认证、仅绑定本机。
不使用/修改已有 Docker 数据库，也不启动 Homebrew 全局数据库服务。
数据库不随前后端退出而停止，可以单独管理：

```sh
.venv/bin/python scripts/local-postgres.py status
.venv/bin/python scripts/local-postgres.py stop
.venv/bin/python scripts/local-postgres.py start
```

可设置 `PG_BIN` 指定 PostgreSQL bin 目录。停止数据库前请先停止使用它的后端。

## 配置与秘密

`backend/api/app_config.json`（0600、Git 和 Docker 构建上下文均忽略）保存：

- root_name：admin；随机管理员密码在 root_pwd。
- invite_code、jwt_key：本地随机生成，不连接线上认证。
- database_url：本地 PostgreSQL 连接地址；不要分享、提交或输出此值。

环境变量 DATABASE_URL 优先于配置文件 database_url，不再回退 SQLite。
连接地址只支持 postgres:// 或 postgresql://，使用专用数据库的 public schema。
当前本地连接无需 URL 查询参数。秘密文件集中在被忽略的 .local 下。
请不要把连接 URL/密码作为终端命令参数或提交到仓库。

## 同步更新表

参考 [SOSDx init_database.py](https://github.com/Fuzhou-U-ACM-SOSD/SOSDx/blob/dev/scripts/init_database.py)
的初始化/存量升级流程实现，但不引入其业务表或清理/重置逻辑。
模型仍是 `backend/api/models/db_models.py`，无需维护第二套当前结构定义。

```sh
# 检查，不提交任何数据库变动；有差异退出 1，异常退出 2
.venv/bin/python backend/scripts/init_database.py --check
# 补齐新表、新字段、索引/约束；可重复执行
.venv/bin/python backend/scripts/init_database.py
```

安全同步：缺失表、允许为空的字段、有数据库默认值的新字段、缺失索引和约束，
放宽 NOT NULL，以及默认值变化。Python default 不等于数据库 db_default；
需要给已有行自动回填的字段应设置 db_default 或编写数据升级 SQL。

改类型、改名、删字段、收紧 NOT NULL、冲突的约束/索引、有数据表新增无默认值的必填字段，
均拒绝自动猜测。先备份，再添加 `backend/migrations/0002_*.sql` 等显式升级脚本。
脚本执行一次并记录 SHA-256；不可编辑已应用脚本。初始化基线是 0001_initial.sql。
详见 [迁移规则](../backend/migrations/README.md)。额外的未知表不会被自动删除。

整个升级使用 PostgreSQL 事务和 advisory lock，失败回滚。--check 的临时 schema 和
版本表检查也会回滚，不留结构/数据变动。检查/同步需要数据库 CREATE schema 权限。
应用本身禁用 generate_schemas，不在处理请求时隐式改结构；开发启动器先同步再启动。
开发启动器会启动本项目默认本地集群；对非本机 DATABASE_URL 只执行 --check，不自动升级。

## SQLite 数据

本次已把原本地 SQLite 的 4 条项目记录导入 PostgreSQL，其他项目表原本为空。
`backend/db/db.sqlite3` 原文件保留，没有删除或修改；应用不再读取它。

其他 SQLite 数据库的一次性导入（先初始化结构、且目标项目表必须全部为空）：

```sh
.venv/bin/python backend/scripts/import_sqlite.py --sqlite /absolute/path/to/db.sqlite3
```

请在启动应用自动 seed 之前导入。导入按外键顺序、校验 JSON/布尔类型并修复序列；
整体事务执行，拒绝合并到已有数据的目标。不会从线上复制数据。

## 备份与恢复

月度备份已改为 pg_dump custom format，而非复制 SQLite 文件。
目标：`backend/backup/db_YYYY_MM_DD/database.dump`（0600）；旧 SQLite 备份不会覆盖。
pg_dump 客户端版本应不低于服务端，可通过 PG_DUMP_BIN 指定。
手动备份（在本机配置指向本地数据库的前提下）：

```sh
(cd backend && ../.venv/bin/python -c 'from api.models.db_backup import create_monthly_db_backup; create_monthly_db_backup(force=True)')
```

使用同版本 pg_restore 恢复到一个独立空库；通过 PGPASSFILE/受保护环境提供连接凭据，
不要将密码放在命令行。测试已实际备份并恢复临时数据库验证数据。

## 验证

```sh
.venv/bin/python -m pip check
.venv/bin/python -m unittest discover -s backend/tests -v
npm --prefix ui run build
```

集成测试只对 127.0.0.1:55432 的项目集群创建随机命名临时数据库，测试完删除，
不会使用应用配置中的目标数据库。共 14 项检查，覆盖幂等、只读检查、补表/字段/索引/约束、SQLite 导入、数据保留、
危险变更拒绝、版本升级/校验和及备份恢复。

现有前端依赖仍有 109 项安全告警（51 moderate / 30 high / 28 critical），本次未强制升级。
本次没有修改线上部署、推送提交或将生产数据导入本地。
