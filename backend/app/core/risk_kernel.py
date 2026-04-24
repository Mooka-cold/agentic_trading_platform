from __future__ import annotations

import hashlib
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def _cfg_float(
    key: str,
    default: float,
    *,
    db_config: Optional[Dict[str, str]] = None,
    env_name: Optional[str] = None,
) -> float:
    if db_config and key in db_config:
        try:
            return float(db_config[key])
        except Exception:
            pass
    if env_name:
        return _env_float(env_name, default)
    return default


def evaluate_trade_risk(
    *,
    user_id: int,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    confidence: float,
    execution_service: Any,
    db_config: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    reasons: List[str] = []
    reject_code = ""

    min_notional = _cfg_float(
        "RISK_KERNEL_MIN_NOTIONAL_USDT",
        5.0,
        db_config=db_config,
        env_name="RISK_KERNEL_MIN_NOTIONAL_USDT",
    )
    max_order_notional = _cfg_float(
        "RISK_KERNEL_MAX_ORDER_NOTIONAL_USDT",
        25000.0,
        db_config=db_config,
        env_name="RISK_KERNEL_MAX_ORDER_NOTIONAL_USDT",
    )
    max_symbol_notional = _cfg_float(
        "RISK_KERNEL_MAX_SYMBOL_NOTIONAL_USDT",
        50000.0,
        db_config=db_config,
        env_name="RISK_KERNEL_MAX_SYMBOL_NOTIONAL_USDT",
    )
    min_confidence = _cfg_float(
        "RISK_KERNEL_MIN_CONFIDENCE",
        0.0,
        db_config=db_config,
        env_name="RISK_KERNEL_MIN_CONFIDENCE",
    )

    if side not in {"BUY", "SELL"}:
        reject_code = "INVALID_SIDE"
        reasons.append(f"Unsupported side '{side}'")

    if not symbol or "/" not in symbol:
        reject_code = reject_code or "INVALID_SYMBOL"
        reasons.append("Symbol must be in BASE/QUOTE format")

    if not math.isfinite(quantity) or quantity <= 0:
        reject_code = reject_code or "INVALID_QUANTITY"
        reasons.append("Quantity must be a positive finite number")

    if not math.isfinite(price) or price <= 0:
        reject_code = reject_code or "INVALID_PRICE"
        reasons.append("Price must be a positive finite number")

    if not math.isfinite(confidence) or confidence < 0 or confidence > 1:
        reject_code = reject_code or "INVALID_CONFIDENCE"
        reasons.append("Confidence must be within [0, 1]")
    elif confidence < min_confidence:
        reject_code = reject_code or "CONFIDENCE_TOO_LOW"
        reasons.append(
            f"Confidence {confidence:.4f} is below configured minimum {min_confidence:.4f}"
        )

    notional = quantity * price if math.isfinite(quantity) and math.isfinite(price) else 0.0
    if notional < min_notional:
        reject_code = reject_code or "NOTIONAL_TOO_SMALL"
        reasons.append(
            f"Order notional {notional:.4f} is below minimum {min_notional:.4f}"
        )
    if notional > max_order_notional:
        reject_code = reject_code or "ORDER_NOTIONAL_LIMIT"
        reasons.append(
            f"Order notional {notional:.4f} exceeds max per-order {max_order_notional:.4f}"
        )

    symbol_notional = 0.0
    try:
        positions = execution_service.get_all_positions()
        for pos in positions:
            if pos.get("symbol") != symbol:
                continue
            size = float(pos.get("size") or 0.0)
            entry = float(pos.get("entry_price") or 0.0)
            symbol_notional += abs(size * entry)
    except Exception:
        positions = []

    projected_symbol_notional = symbol_notional + abs(notional)
    if projected_symbol_notional > max_symbol_notional:
        reject_code = reject_code or "SYMBOL_EXPOSURE_LIMIT"
        reasons.append(
            f"Projected symbol notional {projected_symbol_notional:.4f} exceeds limit {max_symbol_notional:.4f}"
        )

    portfolio_state = execution_service.check_portfolio_risk()
    if not portfolio_state.get("allowed", True):
        reject_code = reject_code or "PORTFOLIO_LOCKED"
        reasons.append(portfolio_state.get("reason") or "Portfolio risk check failed")

    allowed = len(reasons) == 0
    raw = (
        f"{user_id}|{symbol}|{side}|{quantity:.8f}|{price:.8f}|"
        f"{datetime.now(timezone.utc).isoformat()}"
    )
    risk_check_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    return {
        "allowed": allowed,
        "reject_code": reject_code if not allowed else "",
        "reasons": reasons,
        "risk_check_id": risk_check_id,
        "metrics": {
            "notional": round(notional, 6),
            "current_symbol_notional": round(symbol_notional, 6),
            "projected_symbol_notional": round(projected_symbol_notional, 6),
            "thresholds": {
                "min_notional": min_notional,
                "max_order_notional": max_order_notional,
                "max_symbol_notional": max_symbol_notional,
                "min_confidence": min_confidence,
            },
            "portfolio_allowed": bool(portfolio_state.get("allowed", True)),
            "portfolio_reason": portfolio_state.get("reason", "OK"),
        },
    }
