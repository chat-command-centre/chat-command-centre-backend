from typing import Dict, Any, Literal
from pydantic import BaseModel, Field
from command_centre_python.utils.triggers import (
    TriggerDispatcherBase,
    TriggerEvent,
    Trigger,
    PollingTriggerDispatcher,
)
import threading


class BuildPipelineTriggerFired(TriggerEvent):
    event_data: dict


class BuildPipelineTriggerDispatcher(PollingTriggerDispatcher):
    ci_cd_tool: str  # e.g., 'Jenkins', 'GitHub Actions'
    credentials: Dict[str, str]

    def _poll_and_handle_events(self):
        # Implement build pipeline monitoring logic here
        pass

    def handle_event(self, event_data: dict):
        trigger_event = BuildPipelineTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class BuildPipelineTrigger(Trigger):
    dispatcher: BuildPipelineTriggerDispatcher
    pipeline_name: str
    build_status: Literal["success", "failure"]

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        if event_data.get("pipeline_name") != self.pipeline_name:
            return False
        if event_data.get("build_status") != self.build_status:
            return False
        return True
