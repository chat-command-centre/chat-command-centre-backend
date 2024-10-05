from typing import Dict, Any, Literal, Optional
from pydantic import Field
from command_centre_python.utils.triggers import (
    PollingTriggerDispatcher,
    Trigger,
    TriggerEvent,
)
import threading
from datetime import datetime, timedelta
import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


class CalendarEventTriggerFired(TriggerEvent):
    event_data: dict


class CalendarEventTriggerDispatcher(PollingTriggerDispatcher):
    update_interval: int = 60  # In seconds
    credentials: Credentials
    calendar_id: str = "primary"  # Default to primary calendar

    def start(self):
        super().start()
        self.service = build("calendar", "v3", credentials=self.credentials)
        threading.Thread(target=self._poll_and_handle_events, daemon=True).start()
        logger.info("CalendarEventTriggerDispatcher started")

    def _poll_and_handle_events(self):
        while not self._stop_event.is_set():
            now = datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
            events_result = (
                self.service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=now,
                    maxResults=10,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])

            for event in events:
                self.handle_event(event)
            self._stop_event.wait(self.update_interval)

    def stop(self):
        self._stop_event.set()
        logger.info("CalendarEventTriggerDispatcher stopped")

    def handle_event(self, event_data: dict):
        trigger_event = CalendarEventTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class CalendarEventTrigger(Trigger):
    dispatcher: CalendarEventTriggerDispatcher
    event_type: Optional[Literal["meeting", "reminder", "all_day", "recurring"]] = None
    conditions: Dict[str, Any] = Field(default_factory=dict)

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        # Implement event type checking and additional conditions
        return True
