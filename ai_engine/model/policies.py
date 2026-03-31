from typing import Any, Dict, List
from pydantic import BaseModel, Field


class OrchestrationConfig(BaseModel):
    enabled_analysis_nodes: List[str] = Field(default_factory=lambda: ["analyst", "sentiment", "macro", "onchain"])
    enable_cross_examiner: bool = True
    max_revision_rounds: int = 2


class RoutePolicyItem(BaseModel):
    primary: List[str] = Field(default_factory=list)
    fallback: List[str] = Field(default_factory=list)
    timeout_ms: int = 2000
    freshness_sec: int = 60


class DataRoutingPolicy(BaseModel):
    market: RoutePolicyItem = Field(default_factory=RoutePolicyItem)
    news: RoutePolicyItem = Field(default_factory=RoutePolicyItem)
    onchain: RoutePolicyItem = Field(default_factory=RoutePolicyItem)
    global_rules: Dict[str, Any] = Field(default_factory=dict)
