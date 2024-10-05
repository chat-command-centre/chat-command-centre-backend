import logging
from typing import Dict, List, Callable, Type, Optional
from pydantic import Field
from threading import Lock

from .entities import EntityBase

logger = logging.getLogger(__name__)


class Event:
    """Base class for all events."""

    pass


class EventManager:
    """Centralized event management system."""

    listeners: Dict[str, List[Callable[[Event], None]]] = Field(default_factory=dict)
    triggers: List["Trigger"] = Field(default_factory=list)
    _lock: Lock = Lock()

    def __init__(self):
        self.listeners = {}
        self.triggers = []
        self._lock = Lock()

    def register_trigger(self, trigger: "Trigger"):
        with self._lock:
            self.triggers.append(trigger)
            trigger.dispatcher.event_manager = self  # Pass the EventManager instance
            trigger.dispatcher.start()
            logger.info(f"Registered trigger: {trigger}")

    def unregister_trigger(self, trigger: "Trigger"):
        with self._lock:
            trigger.dispatcher.stop()
            self.triggers.remove(trigger)
            logger.info(f"Unregistered trigger: {trigger}")

    def add_listener(self, event_type: str, callback: Callable[[Event], None]):
        with self._lock:
            if event_type not in self.listeners:
                self.listeners[event_type] = []
            self.listeners[event_type].append(callback)
            logger.info(f"Added listener for event type: {event_type}")

    def remove_listener(self, event_type: str, callback: Callable[[Event], None]):
        with self._lock:
            if event_type in self.listeners:
                self.listeners[event_type].remove(callback)
                logger.info(f"Removed listener for event type: {event_type}")

    async def dispatch(self, event: Event):
        event_type = event.__class__.__name__
        logger.debug(f"Dispatching event: {event_type}")
        async with self._lock:
            listeners = self.listeners.get(event_type, [])
        for callback in listeners:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Error in listener for {event_type}: {e}")

    def stop_all_triggers(self):
        logger.info("Stopping all triggers...")
        with self._lock:
            for trigger in self.triggers:
                trigger.dispatcher.stop()
            self.triggers.clear()

    def dispatch_semantic_event(self, data_entry: DataEntry):
        event_type = "SemanticEvent"
        with self._lock:
            listeners = self.listeners.get(event_type, [])
        for callback in listeners:
            try:
                callback(data_entry)
            except Exception as e:
                logger.error(f"Error in listener for {event_type}: {e}")
