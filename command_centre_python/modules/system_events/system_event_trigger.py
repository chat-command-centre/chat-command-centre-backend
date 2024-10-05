from typing import Dict, Any, Literal, List
from pydantic import BaseModel, Field
from command_centre_python.utils.triggers import (
    TriggerDispatcherBase,
    Trigger,
    TriggerEvent,
)
import threading
import time
import logging
import psutil

logger = logging.getLogger(__name__)


class SystemEventTriggerFired(TriggerEvent):
    event_data: dict


class SystemEventTriggerDispatcher(TriggerDispatcherBase):
    event_types: List[Literal["startup", "shutdown"]]
    _stop_event: threading.Event = threading.Event()

    def start(self):
        threading.Thread(target=self._monitor_system_events, daemon=True).start()
        logger.info("SystemEventTriggerDispatcher started")

    def _monitor_system_events(self):
        last_boot_time = psutil.boot_time()
        while not self._stop_event.is_set():
            current_boot_time = psutil.boot_time()
            if current_boot_time != last_boot_time:
                # System has been rebooted
                last_boot_time = current_boot_time
                if "startup" in self.event_types:
                    self.handle_event({"event_type": "startup"})
            time.sleep(5)  # Check every 5 seconds

    def stop(self):
        self._stop_event.set()
        logger.info("SystemEventTriggerDispatcher stopped")

    def handle_event(self, event_data: dict):
        trigger_event = SystemEventTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class SystemEventTrigger(Trigger):
    dispatcher: SystemEventTriggerDispatcher
    event_type: Literal["startup", "shutdown"]

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        return event_data.get("event_type") == self.event_type
