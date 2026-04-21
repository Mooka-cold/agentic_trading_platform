# 运维与发布手册

## 1. 适用范围

用于日常开发、联调、发布前检查和线上故障排查。

## 2. 环境基线

- Node.js 20.9+
- Python 3.10+
- Docker & Docker Compose
- 前端基线：Vite 5 + React 18 + ESLint 9

## 3. 部署模式

本文档统一支持三种部署模式。关键差异在于前端访问地址和 `BACKEND_URL` 代理目标。

### 3.1 模式 A：全部本地部署

适用场景：功能联调、开发自测、单机演示。

启动方式：

```bash
cd /Users/huangyong/Documents/Qell/ai_trading
docker compose up -d --build
```

默认访问：

- Frontend: `http://localhost:3200`
- Backend API: `http://localhost:3201`
- AI Engine: `http://localhost:3202`

关键点：

- `frontend` 容器内已注入 `BACKEND_URL=http://backend:8000`
- 前端通过 Vite 代理将 `/api` 转发到 `BACKEND_URL`

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
BACKEND_URL=http://<REMOTE_HOST>:3201
```

关键点：

- 浏览器统一访问 `/api/v1/*`
- Vite 开发代理将 `/api/*` 转发到 `BACKEND_URL`

### 3.3 模式 C：本地前端 + 远程后端

适用场景：本地调试 UI，远程复用稳定数据与执行服务。

本地前端建议：

```bash
BACKEND_URL=http://<REMOTE_HOST>:3201 npm run dev
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

| 模式 | BACKEND_URL | 前端访问地址 |
| :--- | :--- | :--- |
| 全本地 | `http://backend:8000`（容器内） | `http://localhost:3200` |
| 全远程 | `http://<REMOTE_HOST>:3201` | `http://<REMOTE_HOST>:3200` |
| 本地前端+远程后端 | `http://<REMOTE_HOST>:3201` | `http://localhost:3200` |

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

### 4.3 交易正确性 Harness

```bash
cd /Users/huangyong/Documents/Qell/ai_trading
make harness-smoke
```

说明：

- `harness-smoke` 为发布前最小正确性闸门，重点覆盖余额契约、开仓新鲜度拒单、幂等、K线固化与指标可用性。

## 5. 常见故障与处理

### 5.1 前端代理请求失败

- 现象：页面可打开但 `/api/v1/*` 返回 404/502。
- 处理：确认启动命令是否设置正确 `BACKEND_URL`，并检查 backend 服务是否可达。

### 5.2 ESLint 9 配置错误

- 现象：提示缺少 `eslint.config.*`。
- 处理：确认 `frontend/eslint.config.js` 存在并可被加载。

### 5.3 前端构建失败

- 现象：`npm run build` 失败或类型错误。
- 处理：先执行 `npm install` 再执行 `npm run lint && npm run build`，根据报错修复后重试。

### 5.5 依赖审计出现高危

- 现象：`npm audit --omit=dev` 出现 high/critical。
- 处理：
  1. 先升级直接依赖。
  2. 必要时锁定传递依赖安全版本。
  3. 重新执行审计与构建验证。

### 5.6 本地前端 + 远程后端请求异常

- 现象：页面可打开但工作流/监控流报 404 或连接失败。
- 排查顺序：
  1. 确认 `BACKEND_URL` 指向远程 `3201`。
  2. 确认远程防火墙放行 `3201`。
  3. 确认 backend 到 ai_engine 的内部调用可用。

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
- `make harness-smoke` 是否 100% 通过。
- 依赖审计是否维持 `critical=0`。
