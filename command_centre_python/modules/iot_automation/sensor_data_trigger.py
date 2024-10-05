from typing import Dict, Any, Literal
from pydantic import BaseModel, Field
from command_centre_python.utils.triggers import (
    PollingTriggerDispatcher,
    Trigger,
    TriggerEvent,
)


class SensorDataTriggerFired(TriggerEvent):
    event_data: dict


class SensorDataTriggerDispatcher(PollingTriggerDispatcher):
    sensor_id: str  # ID of the sensor to monitor

    def _poll_and_handle_events(self):
        # Implement sensor data monitoring logic here
        pass

    def handle_event(self, event_data: dict):
        trigger_event = SensorDataTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class SensorThresholdTrigger(Trigger):
    dispatcher: SensorDataTriggerDispatcher
    threshold_value: float
    condition: Literal["above", "below"]

    def check_conditions(self, event_data: dict) -> bool:
        sensor_value = event_data.get("value")
        if sensor_value is None:
            return False
        if self.condition == "above" and sensor_value > self.threshold_value:
            return True
        if self.condition == "below" and sensor_value < self.threshold_value:
            return True
        return False
