# PostgreSQL 远程部署与迁移

`compose.postgres.yml` 为生产模板。它使用独立 PostgreSQL 18、持久化命名卷、
仅内部数据库网络、非超级用户应用账号，以及只读运行时配置文件。
PostgreSQL 不发布宿主机端口。应用仍使用 60081，上传目录沿用原服务。

## 生产发布目录

在服务器仓库之外建立 0700 的发布目录，配置文件/密码文件为 0600：

```text
~/deployments/Creator_SN/<release>/
  compose.yml                 # 复制 compose.postgres.yml
  .env                        # APP_IMAGE、POSTGRES_IMAGE、DATA_DIR；不放密码
  app_config.json             # 保留原管理员/JWT/CORS，添加 database_url
  secrets/postgres-admin-password
  secrets/postgres-app-password
  backups/final/              # 停写后的 SQLite、原始 WAL 副本、上传归档
```

PostgreSQL 镜像应固定 digest；应用固定唯一发布标签并保存 image ID、源码归档 SHA-256
和 Git 基线。生产 Python 依赖使用 backend/requirements.lock.txt，避免随安装时间漂移。
原管理员密码/JWT key 不应为了迁移而重置，也不能把本地开发密码覆盖到生产。
数据库初始化使用单独管理角色，应用角色不能是 superuser 或 CREATEDB。

## 安全迁移流程

1. 在不影响旧服务的情况下构建镜像、启动 PostgreSQL，创建空正式库和隔离预演库。
2. 用 SQLite backup API 制作一致性快照，并备份上传、配置、原镜像/容器元数据。
3. 对快照副本转换 journal_mode=DELETE，保证单文件可以在只读容器挂载中打开。
4. 初始化隔离库，导入 SQLite；用 verify_sqlite.py 对所有表的每个值作规范化哈希比对。
5. 使用独立端口/上传副本预演网站，验证登录、用户/简历/项目接口、前端和 API 契约。
6. 实际执行 pg_dump，再 pg_restore 到另一个空库，并重复数据校验。
7. 停旧服务写入，提供 503 + Retry-After 维护响应，制作最终离线快照。
   WAL 模式下，即便连接关闭，readonly 源可能无法创建共享内存文件。
   将已停写的原 DB、-wal、-journal **原样复制到私有目录**，另建工作副本执行恢复和
   backup API，输出 DELETE 模式单文件。不能直接 immutable=1 忽略可能包含提交数据的 WAL。
   不要修改原数据库的 journal mode，也不要在仍有写入时直接 cp DB/WAL 当作一致性备份。
8. 导入正式空库并校验；启动内部检查容器，复验 API、数据和备份后才开放正式端口。
9. 原容器停机改名保留；保留旧 SQLite、上传归档、配置和镜像。开放写入前失败可恢复旧容器。

```sh
# 在应用镜像中，挂载受保护配置和只读快照后执行：
python scripts/init_database.py
python scripts/import_sqlite.py --sqlite /migration/db.sqlite3
python scripts/verify_sqlite.py --sqlite /migration/db.sqlite3
python scripts/init_database.py --check
```

导入目标必须为空，拒绝自动覆盖/合并已有数据。不要对已有正式库重复导入。
数据校验只输出行数/是否一致，不输出账号、口令、简历或用户文件内容。

## 已安装的服务端运维入口

本次实际迁移在服务器发布目录安装了下列入口，并以 current 指向该发布目录：

```sh
cd ~/deployments/Creator_SN/current
./schema-sync.sh --check       # 默认只检查，差异退出 1、异常退出 2
./backup.sh                    # 手动生成 PostgreSQL custom-format 备份
```

应用模型升级需先备份、停止写入，之后 `./schema-sync.sh --apply`；此命令会拒绝在
正式 Web 仍运行时升级。完成后使用同目录 Compose 启动并验证，切勿再用旧部署目录
覆盖本次服务。显式数据升级 SQL 放 backend/migrations，已应用版本不可编辑。
未来应用代码更新应建立新发布目录/新镜像，不能只编辑旧目录内源码并继续用旧镜像。

已设置服务器本地时间（CST / UTC+08:00）每天 03:17 自动执行 current/backup.sh。
使用 flock 避免备份并发；原 crontab 保留。日志位于发布目录父级 backup-cron.log。
PostgreSQL custom dump 在既有数据目录 backup/db_*/database.dump，权限 0600。
当前备份在同一服务器上；异地备份、监控告警和保留周期需按实际存储策略另行配置。
数据库备份不替代持续上传文件备份，最终迁移时的上传归档另行保留。

## 回滚限制（重要）

旧 SQLite 仅是切换时的检查点，不会持续同步 PostgreSQL 的新写入。
开放新写入后不可直接“无损”回滚 SQLite。必须先保存最新 PG 备份并审阅、迁回新增数据。
服务端 rollback.sh 因此默认拒绝运行，只有明确完成评估后，使用
`--acknowledge-stale-sqlite` 才允许恢复旧容器；PG 容器、卷和备份不会被删除。

不要运行 `docker compose down -v` 或删除 creatorsn-postgres-data。
不要把远端配置、SQL dump、上传归档或容器 inspect 文件提交到 Git。
# OIDC 更新

启用 OIDC 前须创建并持久保存 `secrets/oidc-signing.pem`，
更新 schema 和部署 compose 后再启动 Web。具体步骤与接口说明见
[`docs/oidc.md`](../docs/oidc.md)。签名密钥不得打包到镜像，不包含在 pg_dump 内。
