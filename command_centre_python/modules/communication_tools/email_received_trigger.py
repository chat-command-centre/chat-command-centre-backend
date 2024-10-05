from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from command_centre_python.utils.triggers import (
    TriggerDispatcherBase,
    TriggerEvent,
    Trigger,
)
import threading
import imaplib
import email
import time


class EmailReceivedTriggerFired(TriggerEvent):
    event_data: dict


class EmailReceivedTriggerDispatcher(TriggerDispatcherBase):
    email_address: str
    credentials: Dict[str, str]
    _stop_event: threading.Event = threading.Event()

    def start(self):
        threading.Thread(target=self._check_email, daemon=True).start()

    def _check_email(self):
        # Implement email checking logic here
        while not self._stop_event.is_set():
            # Placeholder for actual implementation
            time.sleep(10)

    def stop(self):
        self._stop_event.set()

    def handle_event(self, event_data: dict):
        trigger_event = EmailReceivedTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class EmailReceivedTrigger(Trigger):
    dispatcher: EmailReceivedTriggerDispatcher
    sender_email: Optional[str]
    subject_contains: Optional[str]

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        if self.sender_email and event_data.get("sender") != self.sender_email:
            return False
        if self.subject_contains and self.subject_contains not in event_data.get(
            "subject", ""
        ):
            return False
        return True
