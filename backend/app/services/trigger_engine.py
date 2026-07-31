import json
import logging
from sqlalchemy.orm import Session
from app.db.session import SessionLocalUser as SessionLocal
from shared.models.user import UserAutomationRule
from app.core.config import settings
import httpx

logger = logging.getLogger("TriggerEngine")

class TriggerEngine:
    def __init__(self):
        pass

    def evaluate_indicator_rule(self, condition_payload: dict, market_context: dict) -> bool:
        """
        Evaluate if a market indicator condition is met.
        Example condition: {"indicator": "RSI", "operator": "<", "value": 30}
        """
        try:
            indicator = condition_payload.get("indicator")
            operator = condition_payload.get("operator")
            target_value = float(condition_payload.get("value", 0))
            
            # Extract actual value from market context
            indicators = market_context.get("indicators", {})
            actual_value = indicators.get(indicator)
            
            if actual_value is None:
                return False
                
            actual_value = float(actual_value)
            
            if operator == "<": return actual_value < target_value
            if operator == "<=": return actual_value <= target_value
            if operator == ">": return actual_value > target_value
            if operator == ">=": return actual_value >= target_value
            if operator == "==": return actual_value == target_value
            
        except Exception as e:
            logger.error(f"Failed to evaluate indicator rule: {e}")
        return False

    async def trigger_workflow_for_user(self, user_id: str, symbol: str, trigger_source: str, context: dict = None):
        """
        Call the AI Engine to start a workflow for a specific user.
        """
        payload = {
            "symbol": symbol,
            "user_id": user_id,
            "session_id": f"trigger-{trigger_source}-{user_id[:8]}", # Generating a readable session ID prefix
            "trigger_context": context or {}
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{settings.AI_ENGINE_URL}/workflow/trigger", json=payload)
                if resp.status_code == 200:
                    logger.info(f"Successfully triggered workflow for user {user_id} on {symbol}")
                else:
                    logger.error(f"Failed to trigger workflow for {user_id}: {resp.text}")
        except Exception as e:
            logger.error(f"Error calling AI Engine trigger: {e}")

    async def process_market_event(self, symbol: str, market_context: dict):
        """
        Called when new K-line / indicators are solidified.
        """
        db = SessionLocal()
        try:
            # Fetch all active INDICATOR rules
            rules = db.query(UserAutomationRule).filter(
                UserAutomationRule.is_active == True,
                UserAutomationRule.rule_type == "INDICATOR",
                (UserAutomationRule.symbol == symbol) | (UserAutomationRule.symbol == "ALL")
            ).all()
            
            for rule in rules:
                if self.evaluate_indicator_rule(rule.condition_payload, market_context):
                    await self.trigger_workflow_for_user(
                        user_id=str(rule.user_id),
                        symbol=symbol,
                        trigger_source="INDICATOR",
                        context={"rule_id": str(rule.id), "market": market_context}
                    )
        finally:
            db.close()

    async def evaluate_cron_rules(self):
        """
        Evaluate all active CRON rules.
        In a production system, this should use croniter to accurately match cron strings.
        For simplicity here, we assume it triggers if it hasn't triggered recently.
        """
        from datetime import datetime, timezone, timedelta
        from croniter import croniter
        db = SessionLocal()
        try:
            rules = db.query(UserAutomationRule).filter(
                UserAutomationRule.is_active == True,
                UserAutomationRule.rule_type == "CRON"
            ).all()
            
            now = datetime.now(timezone.utc)
            for rule in rules:
                cron_str = rule.condition_payload.get("cron")
                if not cron_str:
                    continue
                
                # Check if it should trigger now
                # Simple logic: if next trigger time is <= now, trigger it
                # We need a reference time. If last_triggered_at is null, we trigger now.
                ref_time = rule.last_triggered_at or (now - timedelta(days=1))
                if ref_time.tzinfo is None:
                    ref_time = ref_time.replace(tzinfo=timezone.utc)
                
                if croniter.is_valid(cron_str):
                    cron = croniter(cron_str, ref_time)
                    next_run = cron.get_next(datetime)
                    if next_run.tzinfo is None:
                        next_run = next_run.replace(tzinfo=timezone.utc)
                        
                    if next_run <= now:
                        # Trigger!
                        await self.trigger_workflow_for_user(
                            user_id=str(rule.user_id),
                            symbol=rule.symbol,
                            trigger_source="CRON",
                            context={"rule_id": str(rule.id)}
                        )
                        # Update last_triggered_at
                        rule.last_triggered_at = now
                        db.commit()
        except Exception as e:
            logger.error(f"Error evaluating CRON rules: {e}")
        finally:
            db.close()

trigger_engine = TriggerEngine()