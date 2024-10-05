from typing import Dict, Any, Literal
from pydantic import BaseModel, Field
from command_centre_python.utils.triggers import (
    TriggerDispatcherBase,
    Trigger,
    TriggerEvent,
    PollingTriggerDispatcher,
)


class PaymentTransactionTriggerFired(TriggerEvent):
    event_data: dict


class PaymentTransactionTriggerDispatcher(PollingTriggerDispatcher):
    payment_provider: str  # e.g., 'Stripe', 'PayPal'
    credentials: Dict[str, str]

    def _poll_and_handle_events(self):
        # Implement payment transaction monitoring logic here
        pass

    def handle_event(self, event_data: dict):
        trigger_event = PaymentTransactionTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class PaymentTransactionTrigger(Trigger):
    dispatcher: PaymentTransactionTriggerDispatcher
    transaction_type: Literal["payment", "refund"]
    amount_condition: Dict[str, Any]  # e.g., {'greater_than': 100}

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        if event_data.get("transaction_type") != self.transaction_type:
            return False
        amount = event_data.get("amount")
        if "greater_than" in self.amount_condition:
            if amount <= self.amount_condition["greater_than"]:
                return False
        if "less_than" in self.amount_condition:
            if amount >= self.amount_condition["less_than"]:
                return False
        return True
