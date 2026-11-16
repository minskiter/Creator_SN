# Creator SN OIDC

参考 `id.mskter.com` 的授权码、PKCE S256、RS256 和应用管理流程，独立实现在本项目内，不复制或部署参考站代码。

## 启用与升级

1. 安装更新后的 `backend/requirements.lock.txt`（测试环境使用 `requirements-dev.lock.txt`）。
2. **备份数据库**，按现有部署流程停止 Web 写入，运行 `backend/scripts/init_database.py`。
   新增 `oidcclient`、`oidccode`、`oidcaccesstoken` 三张独立表，由安全 schema 同步器创建；
   不修改已执行的 `0001_initial.sql`，不改变现有用户、项目、简历数据。
3. 创建持久签名密钥，切勿放进镜像或 Git：

   ```sh
   # 本地默认路径（backend/db 已忽略）
   .venv/bin/python backend/scripts/create_oidc_key.py --path backend/db/oidc-signing.pem
   # 生产：在受保护的 release 目录下运行，并使用对应 Python 环境
   python backend/scripts/create_oidc_key.py --path secrets/oidc-signing.pem
   ```

   密钥以 0600 创建，已有文件会拒绝覆盖；备份后续发布需复用该密钥。
   默认 RSA 3072 位。生产 compose 通过 Docker secret 只读挂载到
   `/run/secrets/oidc_signing_key`。`OIDC_SIGNING_KEY_FILE` 优先于配置中的
   `oidc.signing_key_file`；`OIDC_ISSUER` 优先于 `oidc.issuer`，默认
   `https://creatorsn.com`。Issuer 必须是固定 HTTPS 地址，不从 Host 请求头生成。
4. 重建镜像、更新受保护的部署 compose、启动服务，检查 discovery、JWKS、登录和业务接口。
   缺失密钥时 OIDC 返回 503，不自动生成临时密钥；原有账户登录不依赖此密钥。
5. 反向代理须将 `/.well-known/openid-configuration`、`/oauth/*` 和 `/api/*`
   原样转发到同一后端。SPA 使用 hash 路由，授权确认页是 `/#/oauth/authorize`。
   不记录 token、授权码、Client Secret、Authorization 请求头或登录表单内容。
   `/oauth/authorize` 的代理 access log 应关闭查询串记录，授权响应不得缓存。

生产数据库的已有定时 `pg_dump` 会包含新增三表，**不会包含签名私钥**；私钥需要单独加密备份。
本次只提供单把活跃签名密钥；没有多密钥轮转宽限期。不要随意替换签名密钥，否则尚有效的
ID Token 会校验失败。修改 Client Secret 不会更换签名密钥。

## 管理员应用管理

入口：`/#/admin/applications`，复用 vfluent3 导航与按钮。

- 管理接口 `/api/oidc/clients`：GET、POST；`/{client_id}`：PUT、DELETE；
  `/{client_id}/rotate-secret`：POST。
- 以上所有操作都由后端校验当前数据库权限；未登录 401，非管理员 403。
  前端路由守卫和隐藏菜单不是安全边界。管理员被撤权后，旧登录 JWT 也无法管理应用。
- 禁止公开动态注册，不存在给普通账户开放的创建应用入口。
- public：SPA/原生客户端，无密钥；confidential：服务端，使用 `client_secret_basic`。
  两种客户端都必须使用 PKCE S256。客户端类型不可原地修改。
- 仅接受精确注册的 HTTPS 回调；HTTP 仅允许 localhost、127.0.0.1、::1。
  不允许通配符、URL 认证信息或 fragment。
- 密钥只在创建和重置时显示一次，数据库只保存带随机 salt 的 scrypt 哈希。
  修改应用、停用或重置密钥会撤销已有 Access Token 和待使用授权码。
  删除应用会级联清理授权码和 Access Token。
- 注册接口强制普通用户角色，个人资料修改禁止修改角色。
  管理员判断改为精确角色匹配，并实时读取权限，避免子串匹配与旧 JWT 权限残留。

## 第三方接入

Discovery：`https://creatorsn.com/.well-known/openid-configuration`

| 端点 | 用途 |
| --- | --- |
| `/oauth/authorize` | GET，验证参数后跳转本站登录 / 明确授权确认页 |
| `/oauth/token` | POST，form-urlencoded 授权码换令牌 |
| `/oauth/userinfo` | GET / POST，Authorization: Bearer |
| `/oauth/jwks` | GET，RS256 公钥 |
| `/oauth/revoke` | POST，form-urlencoded 撤销 Access Token |

授权参数：`response_type=code`、`client_id`、`redirect_uri`、
`scope=openid profile email`、`state`、`nonce`、
`code_challenge=BASE64URL(SHA256(code_verifier))`、`code_challenge_method=S256`。
调用方必须随机生成并校验 state，建议始终发送并验证 nonce。
只支持这些参数，不支持 prompt、max_age、response_mode 等扩展参数。
用户登录后必须明确同意或拒绝；普通用户可以给已注册应用授权，但不能添加应用。

Token 请求字段：`grant_type=authorization_code`、`code`、`redirect_uri`、
`code_verifier`、`client_id`。机密客户端另外以 HTTP Basic 发送 Client ID / Secret
（符合 OAuth Basic 编码规则）；不接受 `client_secret_post`。

授权码有效 120 秒，事务及行锁确保单次兑换，重放会撤销对应 Access Token。
Access Token 与 ID Token 有效 900 秒，无 refresh_token、隐式流、密码流或登出端点。
授权码和 Access Token 都以 SHA256 摘要入库，过期记录在后续授权时清理。
Access Token 撤销不会提前使已签发的 ID Token 失效；
依赖方必须验证签名、issuer、audience、有效期、nonce，不应将 ID Token 当做 API Access Token。

`openid` 只返回 sub；`profile` 增加 name / preferred_username；
`email` 仅在账户已有邮箱时返回 email / email_verified=false（本站现有邮箱尚未验证）。
不会把管理员角色、密码、手机或邀请码提供给第三方。
公开 OAuth 端点允许无 Cookie 的跨域调用；应用管理与确认授权仍使用本站 Api-key。

## 验证

```sh
.venv/bin/python -m unittest discover -s backend/tests -v
.venv/bin/python -m pip check
npm --prefix ui run build
```

OIDC 测试只在本机隔离 PostgreSQL 集群创建并删除随机测试库，不操作生产或开发业务数据。
覆盖管理员隔离、注册/资料提权防护、授权同意/拒绝、回调与 PKCE 校验、
RS256/JWKS、nonce、scope 隔离、授权码并发重放、过期、停用/删除、密钥重置、令牌撤销、
API 前缀、跨域预检、缓存头及缺失签名密钥时的失败保护。
