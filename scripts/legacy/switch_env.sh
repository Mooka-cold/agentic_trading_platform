#!/bin/bash

MODE=$1

if [ "$MODE" == "local" ]; then
    echo "🔄 Switching to LOCAL development mode..."
    
    # Backend
    cat > backend/.env <<EOL
PROJECT_NAME="AI Trading Platform (Local)"
DATABASE_USER_URL=postgresql://user_admin:user_password@localhost:3205/ai_trading_users
DATABASE_MARKET_URL=postgresql://market_admin:market_password@localhost:3206/ai_trading_market
REDIS_URL=redis://localhost:3204/0
CHROMA_URL=http://localhost:3203
AI_ENGINE_URL=http://localhost:8001
CRYPTOPANIC_API_KEY=${CRYPTOPANIC_API_KEY}
EOL

    # AI Engine
    cat > ai_engine/.env <<EOL
DATABASE_USER_URL=postgresql://user_admin:user_password@localhost:3205/ai_trading_users
DATABASE_MARKET_URL=postgresql://market_admin:market_password@localhost:3206/ai_trading_market
REDIS_URL=redis://localhost:3204/0
BACKEND_URL=http://localhost:8000
CRYPTOPANIC_API_KEY=${CRYPTOPANIC_API_KEY}
OPENAI_API_KEY=${OPENAI_API_KEY}
LLM_MODEL=qwen-plus
EOL

    # Frontend
    cat > frontend/.env.local <<EOL
NEXT_PUBLIC_API_URL=http://localhost:8000
AI_ENGINE_URL=http://localhost:8001
EOL

    echo "✅ Switched to LOCAL. Run services with 'uvicorn ...'"

elif [ "$MODE" == "docker" ]; then
    echo "🔄 Switching to DOCKER/PROD mode..."
    
    # Backend
    cat > backend/.env <<EOL
DATABASE_USER_URL=postgresql://user_admin:user_password@db-users:5432/ai_trading_users
DATABASE_MARKET_URL=postgresql://market_admin:market_password@db-market:5432/ai_trading_market
REDIS_URL=redis://redis:6379/0
CHROMA_URL=http://chromadb:8000
AI_ENGINE_URL=http://ai-engine:8000
CRYPTOPANIC_API_KEY=${CRYPTOPANIC_API_KEY}
EOL

    # AI Engine
    cat > ai_engine/.env <<EOL
DATABASE_USER_URL=postgresql://user_admin:user_password@db-users:5432/ai_trading_users
DATABASE_MARKET_URL=postgresql://market_admin:market_password@db-market:5432/ai_trading_market
REDIS_URL=redis://redis:6379/0
BACKEND_URL=http://backend:8000
CRYPTOPANIC_API_KEY=${CRYPTOPANIC_API_KEY}
OPENAI_API_KEY=${OPENAI_API_KEY}
LLM_MODEL=qwen-plus
EOL

    # Frontend
    cat > frontend/.env.local <<EOL
NEXT_PUBLIC_API_URL=http://47.89.152.214:3201
AI_ENGINE_URL=http://47.89.152.214:3202
EOL

    echo "✅ Switched to DOCKER. You can now build/deploy."

else
    echo "Usage: ./switch_env.sh [local|docker]"
fi
