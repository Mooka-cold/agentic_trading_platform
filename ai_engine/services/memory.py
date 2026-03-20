import chromadb
from chromadb.config import Settings
from langchain_openai import OpenAIEmbeddings
from typing import List, Dict, Any
import os
import json
from core.config import settings

class MemoryService:
    def __init__(self):
        # Connect to ChromaDB (Running in docker container 'chromadb')
        # host='chromadb', port=8000
        # If running locally without docker network, fallback to local persistence
        chroma_host = os.getenv("CHROMA_HOST", "chromadb")
        chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
        
        try:
            self.client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
        except Exception as e:
            print(f"Warning: Could not connect to ChromaDB HTTP Client ({e}). Falling back to local/in-memory.")
            self.client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIRECTORY)

        # Initialize Embedding Function
        # We use OpenAI Embeddings via LangChain adapter or raw
        # ChromaDB expects an embedding function or computes it by default (using ONNX/SentenceTransformer)
        # To keep it simple and free of OpenAI costs for vectorization if possible, we can use default.
        # But for quality, OpenAI is better. Let's use default (all-MiniLM-L6-v2) for now to save setup.
        # It's built-in to ChromaDB python client.
        
        self.collection = self.client.get_or_create_collection(name="trading_insights")

    def add_insight(self, content: str, metadata: Dict[str, Any]):
        """
        Save a learning/insight from Reflector.
        Metadata should include: symbol, outcome (profit/loss), strategy_type, market_phase
        """
        # Create a unique ID or auto-generate
        import uuid
        insight_id = str(uuid.uuid4())
        
        self.collection.add(
            documents=[content],
            metadatas=[metadata],
            ids=[insight_id]
        )
        print(f"[Memory] Added insight: {content[:50]}...")

    def retrieve_insights(self, query: str, limit: int = 3, filter: Dict[str, Any] = None) -> List[str]:
        """
        Retrieve relevant insights for Strategist based on current market context.
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=limit,
            where=filter # Optional: e.g. {"symbol": "BTC/USDT"}
        )
        
        # Chroma returns a dict of lists
        if results and results['documents']:
            return results['documents'][0]
        return []

    def retrieve_learned_rules(self, limit: int = 5) -> List[str]:
        """
        Retrieve high-quality learned rules (Stage=FINAL) for Strategist.
        """
        # We want insights where type="learned_rule" or stage="FINAL"
        # Chroma where clause supports simple operators.
        # Assuming we store metadata stage="FINAL" for final synthesis
        try:
            results = self.collection.query(
                query_texts=["trading rule mistake lesson"], # Generic query to match rules
                n_results=limit,
                where={"type": "learned_rule"} 
            )
            if results and results['documents']:
                return results['documents'][0]
        except Exception as e:
            print(f"Error retrieving learned rules: {e}")
        return []

# Singleton instance
memory_service = MemoryService()
