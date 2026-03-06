import sys
import os
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.services.paper_trading import PaperTradingService, PaperAccount

# Setup DB Connection
# Use internal docker hostname for DB with correct credentials
DATABASE_URL = os.getenv("DATABASE_USER_URL", "postgresql://user_admin:user_password@db-users:5432/ai_trading_users")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def main():
    # 1. Get Strategy from AI Engine
    print("🤖 Asking AI Engine for strategy...")
    try:
        # Note: Ensure AI Engine is running and port 8002 is accessible
        response = requests.post("http://ai-engine:8000/workflow/run", json={"symbol": "BTC/USDT", "session_id": "paper-test"})
        data = response.json()
        
        if data['status'] != 'success':
            print(f"❌ AI Engine failed: {data}")
            return

        state = data['state']
        strategy = state.get('strategy_proposal')
        verdict = state.get('risk_verdict')

        print(f"💡 Strategy: {strategy['action']} {state['market_data']['symbol']} @ {strategy['entry_price']}")
        
        # 2. Check Risk
        if not verdict or not verdict['approved']:
            print(f"🛡️ Risk Review Rejected: {verdict['message'] if verdict else 'No verdict'}")
            return

        # 3. Execute Trade
        print("✅ Strategy Approved. Executing Paper Trade...")
        db = SessionLocal()
        service = PaperTradingService(db)
        
        # Calculate quantity (e.g., use 10% of balance or fixed amount)
        account = service.get_or_create_account()
        quantity = 0.1 # Fixed for test
        
        order = service.execute_market_order(
            symbol=state['market_data']['symbol'],
            side=strategy['action'],
            quantity=quantity,
            current_price=strategy['entry_price']
        )
        
        print(f"🎉 Order Filled! ID: {order.id}")
        print(f"💰 New Balance: {account.balance}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
