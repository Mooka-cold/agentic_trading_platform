# 🚀 Remote Deployment Guide (Singapore Server)

本文档将指导你如何将 **AI Trading Platform** 部署到海外服务器。

## 1. 服务器准备 (Server Setup)

### 1.1 购买服务器
推荐配置：
*   **Provider**: DigitalOcean, Vultr, AWS, or GCP.
*   **Region**: Singapore (SG) or Tokyo (JP).
*   **OS**: Ubuntu 22.04 LTS.

### 1.2 初始化环境
```bash
# 安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

## 2. GitHub Secrets 配置

为了安全，请在 GitHub 仓库的 **Settings -> Secrets and variables -> Actions** 中配置以下变量：

| Secret Name | Description |
| :--- | :--- |
| `SERVER_HOST` | 你的服务器 IP |
| `SERVER_USER` | SSH 用户名 (通常为 root) |
| `SSH_PRIVATE_KEY` | SSH 私钥 (Ed25519) |
| `CRYPTOPANIC_API_KEY` | CryptoPanic API Key |
| `NEWS_API_KEY` | NewsAPI Key |
| `OPENAI_API_KEY` | OpenAI API Key |
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `POSTGRES_USER_PASSWORD` | User 数据库密码 |
| `POSTGRES_MARKET_PASSWORD` | Market 数据库密码 |

## 3. 混合开发模式 (Hybrid Mode)

*   **Backend / AI / DB**: 部署在远程服务器。
*   **Frontend**: 运行在本地，连接远程 API。

修改本地前端 `.env.local`：
```bash
NEXT_PUBLIC_API_URL=http://<YOUR_SERVER_IP>:3201
```

---
> **安全提示**: 包含真实密钥的详细指南已保存在本地 `DEPLOY_GUIDE.md` 并已加入 `.gitignore`。请勿将其提交到公共代码库。
