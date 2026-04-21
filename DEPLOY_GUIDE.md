# 🚀 Remote Deployment Guide (Singapore Server)

本文档将指导你如何从零开始，将 **AI Trading Platform** 部署到海外服务器（推荐新加坡/香港节点），并配置 GitHub Actions 实现自动化部署。

## 1. 服务器准备 (Server Setup)

### 1.1 购买服务器
推荐配置：
*   **Provider**: DigitalOcean, Vultr, AWS, or GCP.
*   **Region**: Singapore (SG) or Tokyo (JP) —— 延迟低，无墙。
*   **OS**: Ubuntu 22.04 LTS.
*   **Specs**: 2 vCPU / 4GB RAM (最小配置，因为跑了 TimescaleDB 和 AI 模型)。

### 1.2 初始化环境
SSH 登录到你的新服务器：
```bash
ssh root@<YOUR_SERVER_IP>
```

执行以下脚本安装 Docker（含 `docker compose` 插件）：
```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Create project directory
mkdir -p ~/ai_trading
mkdir -p ~/ai_trading/init
cd ~/ai_trading
```

## 2. GitHub Secrets 配置

为了让 GitHub Actions 能自动构建并部署代码到你的服务器，你需要配置以下 Secrets。

进入 GitHub 仓库 -> **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**。

| Secret Name | Description | Example Value |
| :--- | :--- | :--- |
| `SERVER_HOST` | 你的服务器 IP 地址 | (购买后填写，如 `128.199.xx.xx`) |
| `SERVER_USER` | SSH 用户名 | `root` |
| `SSH_PRIVATE_KEY` | 你的 SSH 私钥内容 | `-----BEGIN OPENSSH PRIVATE KEY----- ...` |
| `CRYPTOPANIC_API_KEY` | CryptoPanic API Key | `7371d720fb1a8bd56b84a06ecef86e90da462110` |
| `NEWS_API_KEY` | NewsAPI Key | (需自行申请，或留空) |
| `OPENAI_API_KEY` | OpenAI API Key | (需填入您的 sk-...) |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | (需填入您的 sk-...) |
| `POSTGRES_USER_PASSWORD` | (可选) User DB 密码 | `user_password` |
| `POSTGRES_MARKET_PASSWORD` | (可选) Market DB 密码 | `market_password` |

> **如何获取 SSH Private Key?**
> 在你本地机器上生成一对新的密钥（专门用于 CI/CD）：
> `ssh-keygen -t ed25519 -f ~/.ssh/github_deploy`
> 1. 将公钥 (`github_deploy.pub`) 内容追加到服务器的 `~/.ssh/authorized_keys`。
> 2. 将私钥 (`github_deploy`) 内容复制到 GitHub Secret `SSH_PRIVATE_KEY`。

## 3. 首次部署 (First Deployment)

1.  **提交代码**: 确保本地代码已 commit 并 push 到 `main` 分支。
2.  **触发 Workflow**:
    *   GitHub 会自动检测到 push，并开始运行 `Build and Deploy` workflow。
    *   你可以在仓库的 **Actions** 标签页查看进度。
3.  **验证部署**:
    *   当 Workflow 显示 ✅ Success 后。
    *   SSH 登录服务器，运行 `docker compose -f docker-compose.prod.yml ps`，应看到 `backend / ai-engine / scheduler / crawler / market-streamer` 等服务为 `Up`。
    *   健康检查建议：
        - `curl http://<YOUR_SERVER_IP>:3201/health`
        - `curl http://<YOUR_SERVER_IP>:3202/health`
        - `curl http://<YOUR_SERVER_IP>:3207/health`

## 4. 部署模式说明

当前支持三种模式：

1. **全部本地部署**：前后端与数据都在本地
2. **全部远程部署**：前后端与数据都在远程
3. **本地前端 + 远程后端**：前端本地调试，后端与 AI 在远程

详细变量与排障建议见：

- `docs/OPERATIONS_RUNBOOK.md`

## 5. 混合开发模式 (Hybrid Mode)

为了兼顾开发体验（本地调试）与网络环境（海外服务器），我们采用混合模式：

*   **Backend / AI / DB**: 跑在远程服务器上。
*   **Frontend**: 跑在本地。

### 5.1 本地前端配置
本地前端通过 Vite 代理访问远程 backend，启动时设置 `BACKEND_URL`：

```bash
cd frontend
BACKEND_URL=http://<YOUR_SERVER_IP>:3201 npm run dev
```

现在，打开本地浏览器 `http://localhost:3200`，你操作的每一次点击，都会请求远程服务器上的 API。

## 6. 常见问题

*   **端口不通？**
    *   检查云服务商（AWS Security Group / DigitalOcean Firewall）是否放行了 `3201`, `3202` 端口。
    *   若需要采集服务健康检查，额外放行 `3207`。
*   **数据库连不上？**
    *   默认配置下数据库端口 (`5432`) 未暴露到公网，这是为了安全。如果你需要本地 DBeaver 连接，请使用 SSH Tunnel，或者临时在 `docker-compose.prod.yml` 中解开端口映射注释。
