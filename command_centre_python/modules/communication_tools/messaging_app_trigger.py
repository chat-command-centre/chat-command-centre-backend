from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from command_centre_python.utils.triggers import (
    PollingTriggerDispatcher,
    Trigger,
    TriggerEvent,
)
import threading


class MessagingAppTriggerFired(TriggerEvent):
    event_data: dict


class MessagingAppTriggerDispatcher(PollingTriggerDispatcher):
    platform: str  # e.g., 'Slack', 'Teams'
    credentials: Dict[str, str]
    channels: List[str]

    def _poll_and_handle_events(self):
        # Implement messaging app monitoring logic here
        pass

    def handle_event(self, event_data: dict):
        trigger_event = MessagingAppTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class MessagingAppMessageTrigger(Trigger):
    dispatcher: MessagingAppTriggerDispatcher
    keyword: Optional[str]
    user: Optional[str]

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        content = event_data.get("content", "")
        if self.keyword and self.keyword.lower() not in content.lower():
            return False
        if self.user and event_data.get("user") != self.user:
            return False
        return True
