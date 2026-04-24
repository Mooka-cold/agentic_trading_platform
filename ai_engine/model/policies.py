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


class ExecutionCostProfile(BaseModel):
    expected_return_bps: float
    total_cost_cap_bps: float
    variable_cost_cap_bps: float
    max_price_deviation_bps: Dict[str, float] = Field(default_factory=dict)


class ExecutionCostPolicy(BaseModel):
    fee_round_trip_bps: float = 20.0
    budget_ratio_of_expected_return: float = 0.35
    min_order_quantity: float = 0.01
    default_profile: str = "r120"
    profiles: Dict[str, ExecutionCostProfile] = Field(default_factory=dict)


def default_execution_cost_policy() -> ExecutionCostPolicy:
    return ExecutionCostPolicy(
        fee_round_trip_bps=20.0,
        budget_ratio_of_expected_return=0.35,
        min_order_quantity=0.01,
        default_profile="r120",
        profiles={
            "r80": ExecutionCostProfile(
                expected_return_bps=80.0,
                total_cost_cap_bps=28.0,
                variable_cost_cap_bps=8.0,
                max_price_deviation_bps={"limit": 3.0, "twap": 5.0, "pov": 6.0},
            ),
            "r120": ExecutionCostProfile(
                expected_return_bps=120.0,
                total_cost_cap_bps=42.0,
                variable_cost_cap_bps=22.0,
                max_price_deviation_bps={"limit": 5.0, "twap": 10.0, "pov": 14.0},
            ),
            "r150": ExecutionCostProfile(
                expected_return_bps=150.0,
                total_cost_cap_bps=53.0,
                variable_cost_cap_bps=33.0,
                max_price_deviation_bps={"limit": 6.0, "twap": 12.0, "pov": 18.0},
            ),
        },
    )
