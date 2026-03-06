from typing import Any, Dict, List, Optional


def get_missing_proposal_fields(proposal: Any) -> List[str]:
    if proposal is None:
        return ["action", "reasoning", "confidence", "assumptions"]
    action = str(getattr(proposal, "action", "") or "").upper()
    missing: List[str] = []
    required = ["action", "reasoning", "confidence", "assumptions"]
    if action in ["BUY", "SHORT"]:
        required.extend(["entry_price", "stop_loss", "take_profit", "quantity"])
    elif action in ["SELL", "COVER"]:
        required.append("quantity")
    for field in required:
        value = getattr(proposal, field, None)
        if field == "assumptions":
            if not isinstance(value, list) or len(value) == 0:
                missing.append(field)
            continue
        if field in ["reasoning", "action"]:
            if not value:
                missing.append(field)
            continue
        if value is None:
            missing.append(field)
    return missing


def compute_trade_metrics(action: str, entry: Optional[float], stop_loss: Optional[float], take_profit: Optional[float]) -> Dict[str, Any]:
    if action is None:
        action = ""
    direction = action.upper()
    metrics: Dict[str, Any] = {
        "action": direction,
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "sl_distance_pct": None,
        "rr_ratio": None,
        "sl_side_ok": None,
        "tp_side_ok": None,
        "direction_ok": None
    }
    if entry is None or stop_loss is None or take_profit is None:
        return metrics
    if entry == 0:
        return metrics
    risk = abs(entry - stop_loss)
    reward = abs(take_profit - entry)
    metrics["sl_distance_pct"] = risk / abs(entry)
    metrics["rr_ratio"] = reward / risk if risk > 0 else None
    if direction in ["BUY", "COVER"]:
        metrics["sl_side_ok"] = stop_loss < entry
        metrics["tp_side_ok"] = take_profit > entry
    elif direction in ["SELL", "SHORT", "CLOSE"]:
        metrics["sl_side_ok"] = stop_loss > entry
        metrics["tp_side_ok"] = take_profit < entry
    else:
        metrics["sl_side_ok"] = None
        metrics["tp_side_ok"] = None
    metrics["direction_ok"] = bool(metrics["sl_side_ok"]) and bool(metrics["tp_side_ok"])
    return metrics


def build_fix_suggestions(action: str, entry: Optional[float], stop_loss: Optional[float], take_profit: Optional[float], min_rr: float = 1.5, max_sl_distance_pct: float = 0.03) -> Dict[str, Any]:
    suggestions: Dict[str, Any] = {}
    direction = (action or "").upper()
    if entry is None:
        suggestions["entry_price"] = "Provide entry_price"
        return suggestions
    if stop_loss is None:
        suggestions["stop_loss"] = "Provide stop_loss"
    if take_profit is None:
        suggestions["take_profit"] = "Provide take_profit"
    if stop_loss is None or take_profit is None:
        return suggestions
    risk = abs(entry - stop_loss)
    sl_limit = abs(entry) * max_sl_distance_pct
    if risk > sl_limit:
        if direction == "BUY":
            suggestions["stop_loss"] = round(entry - sl_limit, 4)
        elif direction in ["SELL", "CLOSE"]:
            suggestions["stop_loss"] = round(entry + sl_limit, 4)
    if direction in ["BUY", "COVER"]:
        if stop_loss >= entry:
            suggestions["stop_loss_direction"] = "For BUY, stop_loss must be below entry"
        if take_profit <= entry:
            suggestions["take_profit_direction"] = "For BUY, take_profit must be above entry"
    elif direction in ["SELL", "SHORT", "CLOSE"]:
        if stop_loss <= entry:
            suggestions["stop_loss_direction"] = "For SELL, stop_loss must be above entry"
        if take_profit >= entry:
            suggestions["take_profit_direction"] = "For SELL, take_profit must be below entry"
    if risk > 0:
        target_reward = risk * min_rr
        if direction in ["BUY", "COVER"]:
            suggestions["min_take_profit"] = round(entry + target_reward, 4)
        elif direction in ["SELL", "SHORT", "CLOSE"]:
            suggestions["max_take_profit"] = round(entry - target_reward, 4)
    return suggestions
