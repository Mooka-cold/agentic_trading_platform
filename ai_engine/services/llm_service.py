from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from sqlalchemy import create_engine, text
import pandas as pd
from core.config import settings
from pydantic import BaseModel, Field

# Define output structure
class Signal(BaseModel):
    action: str = Field(description="Action to take: BUY, SELL, or HOLD")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(description="Brief explanation for the decision based on technical and sentiment analysis")

class LLMService:
    def __init__(self):
        # Default from ENV
        openai_api_key = settings.OPENAI_API_KEY
        openai_api_base = settings.OPENAI_API_BASE
        llm_model = settings.LLM_MODEL

        # Try to load from DB
        try:
            user_engine = create_engine(settings.DATABASE_USER_URL)
            with user_engine.connect() as conn:
                result = conn.execute(text("SELECT key, value FROM system_configs"))
                configs = {row[0]: row[1] for row in result.fetchall()}
                
                if "OPENAI_API_KEY" in configs: 
                    openai_api_key = configs["OPENAI_API_KEY"]
                    print("✅ Loaded OPENAI_API_KEY from System Config DB")
                
                if "OPENAI_API_BASE" in configs:
                    openai_api_base = configs["OPENAI_API_BASE"]
                    print(f"✅ Loaded OPENAI_API_BASE from System Config DB: {openai_api_base}")
                
                if "LLM_MODEL" in configs:
                    llm_model = configs["LLM_MODEL"]
                    print(f"✅ Loaded LLM_MODEL from System Config DB: {llm_model}")

        except Exception as e:
            print(f"⚠️ Failed to load config from DB, falling back to ENV: {e}")

        self.model_name = llm_model
        self.llm = ChatOpenAI(
            model=llm_model,
            openai_api_key=openai_api_key,
            openai_api_base=openai_api_base,
            temperature=0.2 
        )
        self.engine = create_engine(settings.DATABASE_MARKET_URL)
        self.parser = JsonOutputParser(pydantic_object=Signal)

    def get_market_data(self, symbol: str, interval: str = "1m", limit: int = 50) -> str:
        """Fetch recent OHLCV data and calculate basic indicators"""
        query = text("""
            SELECT time, open, high, low, close, volume 
            FROM market_klines 
            WHERE symbol = :symbol AND interval = :interval
            ORDER BY time DESC
            LIMIT :limit
        """)
        
        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"symbol": symbol, "interval": interval, "limit": limit})
        
        if df.empty:
            return "No market data available."
            
        # Sort by time ASC for analysis
        df = df.sort_values("time")
        
        # Calculate simple indicators (e.g. SMA)
        df['SMA_10'] = df['close'].rolling(window=10).mean()
        df['RSI'] = self.calculate_rsi(df['close'])
        
        # Convert to string summary (last 5 rows)
        summary = df.tail(5).to_string()
        return summary

    def calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    async def analyze(self, symbol: str) -> dict:
        """
        Analyze market data using LLM and generate a trading signal.
        """
        market_context = self.get_market_data(symbol)
        
        # Prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert crypto trading analyst. Analyze the provided market data and generate a trading signal."),
            ("user", "Symbol: {symbol}\n\nMarket Data (OHLCV + Indicators):\n{market_data}\n\nBased on the technical indicators (RSI, SMA, Price Action), what is your recommendation? Return JSON with action, confidence, and reasoning.\n\n{format_instructions}")
        ])
        
        chain = prompt | self.llm | self.parser
        
        try:
            result = await chain.ainvoke({
                "symbol": symbol,
                "market_data": market_context,
                "format_instructions": self.parser.get_format_instructions()
            })
            if isinstance(result, dict):
                result["model_used"] = self.model_name
            return result
        except Exception as e:
            print(f"LLM Error: {e}")
            return {"action": "HOLD", "confidence": 0.0, "reasoning": f"Error during analysis: {str(e)}", "model_used": self.model_name}
