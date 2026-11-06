# Creator SN frontend

Vue 3 + Vite + `@creatorsn/vfluent3`。
完整安装、账号和启动说明见 [本地开发环境](../docs/development.md)。

```sh
npm ci
npm run dev -- --host 127.0.0.1 --port 8080 --strictPort
npm run build
```

开发 API 依赖 8000 端口上的本地后端，建议使用仓库根目录的一键启动脚本。
`npm run api` 可重新生成客户端（需先启动后端；会更改 `src/api`）。
不混用 Yarn；本仓库没有配置 lint/test 命令。
