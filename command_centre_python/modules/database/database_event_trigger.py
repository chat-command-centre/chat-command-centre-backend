from typing import Dict, Any, List, Literal
from pydantic import BaseModel, Field
from command_centre_python.utils.triggers import (
    PollingTriggerDispatcher,
    Trigger,
    TriggerEvent,
)
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine


class DatabaseEventTriggerFired(TriggerEvent):
    event_data: dict


class DatabaseEventTriggerDispatcher(TriggerDispatcherBase):
    database_url: str
    tables: List[str]
    engine: Engine = None

    def start(self):
        self.engine = create_engine(self.database_url)
        for table in self.tables:

            @event.listens_for(self.engine, "after_insert", named=True)
            def receive_after_insert(mapper, connection, target):
                self.handle_event(
                    {"operation": "insert", "table": table, "data": target.__dict__}
                )

            # Similar events can be set up for update and delete

    def stop(self):
        if self.engine:
            self.engine.dispose()

    def handle_event(self, event_data: dict):
        trigger_event = DatabaseEventTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class DatabaseEventTrigger(Trigger):
    dispatcher: DatabaseEventTriggerDispatcher
    table_name: str
    operation: Literal["insert", "update", "delete"]

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        if event_data.get("operation") != self.operation:
            return False
        if event_data.get("table") != self.table_name:
            return False
        return True
