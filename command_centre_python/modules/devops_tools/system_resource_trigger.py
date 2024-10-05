from typing import Dict, Any, Literal
from pydantic import BaseModel, Field
from command_centre_python.utils.triggers import (
    PollingTriggerDispatcher,
    Trigger,
    TriggerEvent,
)
import psutil  # For system resource monitoring


class SystemResourceTriggerFired(TriggerEvent):
    event_data: dict


class SystemResourceTriggerDispatcher(PollingTriggerDispatcher):
    resource_type: Literal["cpu", "memory", "disk"]
    threshold: float  # Percentage

    def _poll_and_handle_events(self):
        usage = self._get_resource_usage()
        if usage is not None:
            self.handle_event({"usage": usage})

    def _get_resource_usage(self) -> Optional[float]:
        if self.resource_type == "cpu":
            return psutil.cpu_percent()
        elif self.resource_type == "memory":
            return psutil.virtual_memory().percent
        elif self.resource_type == "disk":
            return psutil.disk_usage("/").percent
        else:
            return None

    def handle_event(self, event_data: dict):
        trigger_event = SystemResourceTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class SystemResourceThresholdTrigger(Trigger):
    dispatcher: SystemResourceTriggerDispatcher
    condition: Literal["above", "below"]
    threshold_value: float

    def check_conditions(self, event_data: dict) -> bool:
        usage = event_data.get("usage")
        if usage is None:
            return False
        if self.condition == "above" and usage > self.threshold_value:
            return True
        if self.condition == "below" and usage < self.threshold_value:
            return True
        return False
