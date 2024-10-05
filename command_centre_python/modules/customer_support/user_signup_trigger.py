from typing import Dict, Any
from pydantic import BaseModel, Field
from command_centre_python.utils.triggers import (
    TriggerDispatcherBase,
    Trigger,
    TriggerEvent,
    PollingTriggerDispatcher,
)


class UserSignupTriggerFired(TriggerEvent):
    event_data: dict


class UserSignupTriggerDispatcher(PollingTriggerDispatcher):
    platform: str  # e.g., 'Website', 'MobileApp'

    def _poll_and_handle_events(self):
        # Implement user signup monitoring logic here
        pass

    def handle_event(self, event_data: dict):
        trigger_event = UserSignupTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class UserSignupTrigger(Trigger):
    dispatcher: UserSignupTriggerDispatcher
    conditions: Dict[str, Any]  # Conditions on user data

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        for key, value in self.conditions.items():
            if event_data.get(key) != value:
                return False
        return True
