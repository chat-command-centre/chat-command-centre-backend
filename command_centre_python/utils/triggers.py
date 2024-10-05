from abc import ABC, abstractmethod
from typing import Dict, Any, TYPE_CHECKING, Callable, List
from pydantic import BaseModel
import asyncio

from .entities import DataEntry, DataSource
from .event_manager import EventManager

if TYPE_CHECKING:
    from ..core.event_manager import EventManager


class Event(BaseModel):
    """Base class for all events."""

    pass


class TriggerEvent(Event):
    """Base class for all trigger events."""

    pass


class TriggerDispatcherBase(ABC):
    event_manager: "EventManager" = None

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    def dispatch(self, event: "TriggerEvent"):
        """Dispatch event via the EventManager."""
        if self.event_manager:
            self.event_manager.dispatch(event)
        else:
            raise Exception("EventManager not set for dispatcher")


class Trigger(ABC):
    dispatcher: TriggerDispatcherBase

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        raise NotImplementedError


class PollingTriggerDispatcher(TriggerDispatcherBase):
    update_interval: int = 60  # Default interval in seconds

    @abstractmethod
    def _poll_and_handle_events(self):
        pass

    def start(self):
        # Implement a mechanism to periodically call _poll_and_handle_events
        pass

    def stop(self):
        # Implement stopping mechanism
        pass


class SemanticTrigger:
    def __init__(self, condition: str, action: Callable):
        self.condition = condition
        self.action = action

    async def evaluate(self, data_entry: DataEntry, metadata: Dict[str, Any] = None):
        response = await llm_evaluate_condition(self.condition, data_entry)
        result = response.strip().lower()
        if result == "true":
            await self.action(data_entry, metadata)


@ell.simple(model="gpt-4")
async def llm_evaluate_condition(condition: str, data_entry: DataEntry) -> bool:
    """You are an assistant that evaluates conditions based on data entries."""
    return f"Condition: {condition}\nData: {data_entry.data}\nIs the condition met? Reply with 'True' or 'False'."


async def invoke_trigger_by_name(
    trigger_name: str, params: Dict[str, Any], metadata: Dict[str, Any]
):
    trigger = get_trigger_by_name(trigger_name)
    if trigger:
        # Use metadata in the action call
        data_entry = DataEntry(data=params)
        await trigger.evaluate(data_entry, metadata)
    else:
        raise ValueError(f"Trigger '{trigger_name}' not found.")


def get_trigger_by_name(name: str):
    # Implementation to retrieve the trigger instance by name
    # This could involve searching a registry or database of triggers
    pass


class SemanticTriggerDispatcher:
    def __init__(self, event_manager: EventManager):
        self.event_manager = event_manager
        self.triggers: List[SemanticTrigger] = []

    def register_trigger(self, trigger: SemanticTrigger):
        self.triggers.append(trigger)

    async def monitor_data_sources(self):
        # This method should be called periodically or when data sources are updated
        for data_source in DataSource.get_all():
            for data_entry in data_source.data_entries:
                for trigger in self.triggers:
                    await trigger.evaluate(data_entry)

    async def start(self):
        while True:
            await self.monitor_data_sources()
            await asyncio.sleep(10)  # Adjust the interval as needed


# You can keep general-purpose trigger classes here if needed
