import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())
# Add ai_engine subdirectory to path
sys.path.append(os.path.join(os.getcwd(), 'ai_engine'))

print("Attempting to import ai_engine.main...")
try:
    from ai_engine import main
    print("✅ Import successful!")
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()

print("\nAttempting to instantiate MarketDataService...")
try:
    from ai_engine.services.market_data import market_data_service
    print("✅ MarketDataService instantiated!")
except Exception as e:
    print(f"❌ MarketDataService failed: {e}")
    traceback.print_exc()
