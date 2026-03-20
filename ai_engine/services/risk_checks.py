from typing import Any, Dict, List, Optional


def get_missing_proposal_fields(proposal: Any) -> List[str]:
    if proposal is None:
        return ["action", "reasoning", "confidence", "assumptions"]
    action = str(getattr(proposal, "action", "") or "").upper()
    missing: List[str] = []
    required = ["action", "reasoning", "confidence", "assumptions"]
    if action in ["BUY", "SHORT"]:
        required.extend(["entry_price", "stop_loss", "take_profit", "quantity"])
    elif action in ["SELL", "COVER", "CLOSE"]:
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

    # --- Fix 1: Determine Trade Direction ---
    # LONG/BUY: Entry < TP, Entry > SL
    # SHORT/SELL: Entry > TP, Entry < SL
    is_long = direction in ["BUY", "LONG", "COVER"] # COVER is closing a SHORT, effectively buying back
    is_short = direction in ["SELL", "SHORT", "CLOSE"] # CLOSE could be selling a LONG
    
    # Refined Logic for CLOSE/COVER/SELL:
    # If action is 'SELL' but we hold a LONG position, it's a closing action. 
    # But here we are validating the PRICE logic.
    # If action is 'SELL', we are selling at Entry. 
    # Standard: Sell High (Entry), Buy Low. 
    # Wait, 'SELL' usually means Open Short OR Close Long.
    # In our system:
    # LONG = Open Long
    # SHORT = Open Short
    # SELL = Close Long (Selling the asset)
    # COVER = Close Short (Buying back)
    
    # Validation logic depends on INTENT.
    # For OPENING positions:
    # LONG: SL < Entry < TP
    # SHORT: TP < Entry < SL
    
    # For CLOSING positions (SELL/COVER):
    # We don't usually set SL/TP for a closing order itself (it IS the exit).
    # But if Strategist outputs SL/TP for a CLOSE order, it might mean "Close partial now, set SL/TP for remainder".
    # Or it's just a mistake.
    # Our Reviewer skips checks for non-opening trades, so this function matters most for LONG/SHORT.

    if direction in ["LONG", "BUY"]:
        metrics["sl_side_ok"] = stop_loss < entry
        metrics["tp_side_ok"] = take_profit > entry
    elif direction in ["SHORT", "SELL"]: # Assuming SELL can be Open Short in some contexts, but let's stick to SHORT
        metrics["sl_side_ok"] = stop_loss > entry
        metrics["tp_side_ok"] = take_profit < entry
    else:
        # For COVER/CLOSE/HOLD, we default to True or None to avoid blocking
        metrics["sl_side_ok"] = True 
        metrics["tp_side_ok"] = True

    metrics["direction_ok"] = bool(metrics["sl_side_ok"]) and bool(metrics["tp_side_ok"])
    
    risk = abs(entry - stop_loss)
    reward = abs(take_profit - entry)
    
    if entry != 0:
        metrics["sl_distance_pct"] = risk / entry
    
    metrics["rr_ratio"] = reward / risk if risk > 0 else 0.0
    
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
        if direction in ["BUY", "LONG"]:
            suggestions["stop_loss"] = round(entry - sl_limit, 4)
        elif direction in ["SELL", "SHORT", "CLOSE"]:
            suggestions["stop_loss"] = round(entry + sl_limit, 4)
    
    if direction in ["BUY", "LONG", "COVER"]:
        if stop_loss >= entry:
            suggestions["stop_loss_direction"] = "For LONG/BUY, stop_loss must be below entry"
        if take_profit <= entry:
            suggestions["take_profit_direction"] = "For LONG/BUY, take_profit must be above entry"
            
    elif direction in ["SELL", "SHORT", "CLOSE"]:
        if stop_loss <= entry:
            suggestions["stop_loss_direction"] = "For SHORT/SELL, stop_loss must be above entry"
        if take_profit >= entry:
            suggestions["take_profit_direction"] = "For SHORT/SELL, take_profit must be below entry"
            
    if risk > 0:
        target_reward = risk * min_rr
        if direction in ["BUY", "LONG", "COVER"]:
            suggestions["min_take_profit"] = round(entry + target_reward, 4)
        elif direction in ["SELL", "SHORT", "CLOSE"]:
            suggestions["max_take_profit"] = round(entry - target_reward, 4)
    return suggestions
