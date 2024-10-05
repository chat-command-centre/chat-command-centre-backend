from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from command_centre_python.utils.triggers import (
    PollingTriggerDispatcher,
    Trigger,
    TriggerEvent,
)
import time


class ErrorLogTriggerFired(TriggerEvent):
    event_data: dict


class ErrorLogTriggerDispatcher(PollingTriggerDispatcher):
    log_file_path: str
    error_level: Literal["ERROR", "WARNING", "CRITICAL"]
    _last_position: int = 0

    def _poll_and_handle_events(self):
        with open(self.log_file_path, "r") as log_file:
            log_file.seek(self._last_position)
            lines = log_file.readlines()
            self._last_position = log_file.tell()
            for line in lines:
                if self.error_level in line:
                    self.handle_event(
                        {"message": line.strip(), "level": self.error_level}
                    )

    def handle_event(self, event_data: dict):
        trigger_event = ErrorLogTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class ErrorLogTrigger(Trigger):
    dispatcher: ErrorLogTriggerDispatcher
    error_message_contains: Optional[str]

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        if (
            self.error_message_contains
            and self.error_message_contains not in event_data.get("message", "")
        ):
            return False
        return True
