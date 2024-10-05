from typing import Dict, Any
from pydantic import BaseModel, Field
from command_centre_python.utils.triggers import (
    TriggerDispatcherBase,
    TriggerEvent,
    Trigger,
)
import threading
import time
from datetime import datetime
from croniter import croniter


class TimeTriggerFired(TriggerEvent):
    event_data: dict


class TimeTriggerDispatcher(TriggerDispatcherBase):
    schedule: str  # e.g., cron expression
    _stop_event: threading.Event = Field(default_factory=threading.Event)

    def start(self):
        threading.Thread(target=self._run_schedule, daemon=True).start()

    def _run_schedule(self):
        cron = croniter(self.schedule, datetime.now())
        while not self._stop_event.is_set():
            next_run = cron.get_next(datetime)
            wait_time = (next_run - datetime.now()).total_seconds()
            if self._stop_event.wait(wait_time):
                break
            self.handle_event({"timestamp": datetime.utcnow().isoformat()})

    def stop(self):
        self._stop_event.set()

    def handle_event(self, event_data: dict):
        trigger_event = TimeTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class TimeTrigger(Trigger):
    dispatcher: TimeTriggerDispatcher
    time_conditions: Dict[str, Any]  # e.g., {'hour': 14, 'minute': 30}

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        timestamp = event_data.get("timestamp")
        if not timestamp:
            return False
        event_time = datetime.fromisoformat(timestamp)
        for key, value in self.time_conditions.items():
            if getattr(event_time, key) != value:
                return False
        return True
