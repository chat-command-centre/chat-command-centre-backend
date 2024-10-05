from typing import Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from command_centre_python.utils.triggers import (
    PollingTriggerDispatcher,
    Trigger,
    TriggerEvent,
)


class WeatherAlertTriggerFired(TriggerEvent):
    event_data: dict


class WeatherService:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_alerts(self, location: str, alert_types: List[str]) -> List[dict]:
        # Implement API call to weather service
        # Placeholder implementation
        return [
            {
                "type": "storm",
                "severity": "high",
                "description": "Severe thunderstorm warning",
                "start_time": datetime.now().isoformat(),
                "end_time": (datetime.now() + timedelta(hours=2)).isoformat(),
            }
        ]


class WeatherAlertTriggerDispatcher(PollingTriggerDispatcher):
    location: str
    alert_types: List[str]
    api_key: str

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.weather_service = WeatherService(self.api_key)

    def _poll_and_handle_events(self):
        alerts = self.weather_service.get_alerts(self.location, self.alert_types)
        for alert in alerts:
            self.handle_event(alert)

    def handle_event(self, event_data: dict):
        trigger_event = WeatherAlertTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class WeatherAlertTrigger(Trigger):
    dispatcher: WeatherAlertTriggerDispatcher
    alert_type: str  # e.g., 'storm', 'heatwave'
    conditions: Dict[str, Any]

    def check_conditions(self, event_data: dict) -> bool:
        if event_data["type"] != self.alert_type:
            return False

        for key, value in self.conditions.items():
            if key not in event_data or event_data[key] != value:
                return False

        return True
