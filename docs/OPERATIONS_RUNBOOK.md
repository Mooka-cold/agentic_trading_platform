# 运维与发布手册

## 1. 适用范围

用于日常开发、联调、发布前检查和线上故障排查。

## 2. 环境基线

- Node.js 20.9+
- Python 3.10+
- Docker & Docker Compose
- 前端基线：Next.js 16 + ESLint 9

## 3. 部署模式

本文档统一支持三种部署模式。关键差异在于前端访问地址和环境变量。

### 3.1 模式 A：全部本地部署

适用场景：功能联调、开发自测、单机演示。

启动方式：

```bash
cd /Users/huangyong/Documents/Qell/ai_trading
docker compose up -d
```

默认访问：

- Frontend: `http://localhost:3200`
- Backend API: `http://localhost:3201`
- AI Engine: `http://localhost:3202`

关键点：

- `frontend` 容器内已注入 `NEXT_PUBLIC_API_URL=http://localhost:3201`
- `frontend` 代理 AI Engine 使用 `AI_ENGINE_URL=http://ai-engine:8000`

### 3.2 模式 B：全部远程部署

适用场景：线上环境、团队共享环境。

推荐步骤：

1. 远程机器启动核心服务（后端/引擎/数据）：

```bash
cd ~/ai_trading
docker compose -f docker-compose.prod.yml up -d
```

2. 前端部署到远程（Node 进程或容器均可），确保以下变量正确：

```bash
NEXT_PUBLIC_API_URL=http://<REMOTE_HOST>:3201
AI_ENGINE_URL=http://<REMOTE_HOST>:3202
```

关键点：

- 浏览器请求走 `NEXT_PUBLIC_API_URL`
- Next.js 服务端代理 `/api/ai_engine/*` 走 `AI_ENGINE_URL`

### 3.3 模式 C：本地前端 + 远程后端

适用场景：本地调试 UI，远程复用稳定数据与执行服务。

本地前端 `.env.local` 建议：

```bash
NEXT_PUBLIC_API_URL=http://<REMOTE_HOST>:3201
AI_ENGINE_URL=http://<REMOTE_HOST>:3202
```

启动：

```bash
cd frontend
npm install
npm run dev
```

访问：

- 本地前端：`http://localhost:3200`
- API 实际指向远程服务

### 3.4 三种模式变量对照

| 模式 | NEXT_PUBLIC_API_URL | AI_ENGINE_URL | 前端访问地址 |
| :--- | :--- | :--- | :--- |
| 全本地 | `http://localhost:3201` | `http://localhost:3202` | `http://localhost:3200` |
| 全远程 | `http://<REMOTE_HOST>:3201` | `http://<REMOTE_HOST>:3202` | `http://<REMOTE_HOST>:3200` |
| 本地前端+远程后端 | `http://<REMOTE_HOST>:3201` | `http://<REMOTE_HOST>:3202` | `http://localhost:3200` |

## 4. 发布前最小检查

### 4.1 前端

```bash
cd frontend
npm install
npm audit --omit=dev
npm run lint
npm run build
```

### 4.2 后端与引擎

```bash
cd ai_engine
python -m py_compile agents/portfolio_manager.py
```

## 5. 常见故障与处理

### 5.1 前端构建失败：Turbopack 与 webpack 配置冲突

- 现象：Next 16 构建时报 Turbopack/webpack 冲突。
- 处理：确认 `frontend/package.json` 的 `dev/build` 使用 `--webpack`。

### 5.2 ESLint 9 配置错误

- 现象：提示缺少 `eslint.config.*`。
- 处理：确认 `frontend/eslint.config.mjs` 存在并可被加载。

### 5.3 API Route 类型不匹配

- 现象：Next build 报 route handler 第二参数类型错误。
- 处理：使用 Next 16 约定签名（`context.params` 为 Promise）。

### 5.4 前端构建期 localStorage 报错

- 现象：构建阶段出现 `localStorage.getItem is not a function`。
- 处理：将依赖浏览器对象的 Provider 放入 Client 组件动态加载路径。

### 5.5 依赖审计出现高危

- 现象：`npm audit --omit=dev` 出现 high/critical。
- 处理：
  1. 先升级直接依赖（如 next）。
  2. 对传递依赖使用 `overrides` 固定安全版本。
  3. 重新执行审计与构建验证。

### 5.6 本地前端 + 远程后端请求异常

- 现象：页面可打开但工作流/监控流报 404 或连接失败。
- 排查顺序：
  1. 确认 `.env.local` 中 `NEXT_PUBLIC_API_URL` 指向远程 `3201`。
  2. 确认 `.env.local` 中 `AI_ENGINE_URL` 指向远程 `3202`。
  3. 确认远程防火墙放行 `3201/3202`。

## 6. 回滚流程

### 6.1 依赖层回滚

```bash
cd frontend
npm install
npm run lint
npm run build
```

### 6.2 代码层回滚

- 回滚到上一个稳定提交后，重新执行发布前最小检查。
- 若为会话流程问题，优先验证 reviewer 拒绝链路与 PM 修订链路。

## 7. 值班检查清单

- 工作流会话是否持续推进（无卡死轮次）。
- 风控拒绝是否带 reject_code 与 fix_suggestions。
- 前端历史页是否可查看完整会话日志与 artifact。
- 依赖审计是否维持 `critical=0`。
