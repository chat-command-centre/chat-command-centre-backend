from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from command_centre_python.utils.triggers import (
    PollingTriggerDispatcher,
    Trigger,
    TriggerEvent,
)


class SocialMediaTriggerFired(TriggerEvent):
    event_data: dict


class SocialMediaTriggerDispatcher(PollingTriggerDispatcher):
    platform: str  # e.g., 'Twitter', 'Facebook'
    credentials: Dict[str, str]
    keywords: List[str]

    def _poll_and_handle_events(self):
        # Implement social media monitoring logic here
        pass

    def handle_event(self, event_data: dict):
        trigger_event = SocialMediaTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class SocialMediaMentionTrigger(Trigger):
    dispatcher: SocialMediaTriggerDispatcher
    keyword: str
    user_handle: Optional[str]

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        if self.keyword.lower() in event_data.get("content", "").lower():
            if self.user_handle and event_data.get("user") != self.user_handle:
                return False
            return True
        return False
