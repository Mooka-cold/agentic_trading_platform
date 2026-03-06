# MCP 回归测试套件

## 目标
通过 Chrome DevTools MCP 执行端到端回归验证，覆盖首页、历史、设置与连续模式，以及关键 API 任务触发。

## 套件文件
- regression_suite.json：可复用测试步骤定义

## 执行前置条件
- Docker 服务已启动：backend、ai-engine、frontend、scheduler
- 前端地址：`http://localhost:3200`
- 后端地址：`http://localhost:3201`

## 执行方式
### 一键执行（推荐）
```bash
cd tests/mcp
npm install
npx playwright install chromium
npm run test:mcp
```

执行完成后会在 `tests/mcp/output/<timestamp>/` 生成 `report.md` 与失败截图。

### 手动执行（MCP 工具）
使用 MCP 工具执行 `regression_suite.json` 的步骤，包含：
1. 导航至首页并校验标题
2. 校验 Market Intelligence 渲染
3. 进入 History 页面校验 Session 列表
4. 进入 Settings 页面并测试 Continuous Mode 启停
5. 触发后台 Job 接口并检查返回状态
6. 检查 Console 与 Network 错误

## 失败定位建议
- 页面空白：先检查 `backend` 和 `ai-engine` 是否健康
- 历史列表为空：检查 `/api/v1/workflow/history` 返回
- Continuous Mode 启停失败：检查 `/api/v1/workflow/run` 与 `/api/v1/workflow/stop`
- 新闻列表为空：检查 `/api/v1/news` 与 `NEWS_API_KEY`
