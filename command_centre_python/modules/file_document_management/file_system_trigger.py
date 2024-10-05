from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field
from command_centre_python.utils.triggers import (
    TriggerDispatcherBase,
    Trigger,
    TriggerEvent,
)
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
import fnmatch
import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class FileSystemChangeTriggerFired(TriggerEvent):
    event_data: dict


class FileSystemTriggerDispatcher(TriggerDispatcherBase):
    path: str
    event_types: List[Literal["modified", "created", "deleted", "moved"]]
    file_patterns: List[str] = Field(default_factory=lambda: ["*"])
    _observer: Optional[Observer] = None
    _event_handler: Optional[FileSystemEventHandler] = None
    _stop_event: threading.Event = threading.Event()

    def start(self):
        self._event_handler = self._create_event_handler()
        self._observer = Observer()
        self._observer.schedule(self._event_handler, self.path, recursive=True)
        self._observer.start()
        logger.info(f"FileSystemTriggerDispatcher started monitoring {self.path}")

    def _create_event_handler(self) -> FileSystemEventHandler:
        dispatcher = self

        class Handler(FileSystemEventHandler):
            def on_any_event(self, event: FileSystemEvent):
                if event.is_directory:
                    return
                event_type = (
                    event.event_type
                )  # 'modified', 'created', 'deleted', 'moved'
                if event_type not in dispatcher.event_types:
                    return
                for pattern in dispatcher.file_patterns:
                    if fnmatch.fnmatch(event.src_path, pattern):
                        event_data = {
                            "event_type": event_type,
                            "src_path": event.src_path,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                        dispatcher.handle_event(event_data)
                        break

        return Handler()

    def stop(self):
        self._observer.stop()
        self._observer.join()
        self._stop_event.set()
        logger.info("FileSystemTriggerDispatcher stopped")

    def handle_event(self, event_data: dict):
        trigger_event = FileSystemChangeTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class FileSystemChangeTrigger(Trigger):
    dispatcher: FileSystemTriggerDispatcher
    conditions: Dict[str, Any] = Field(default_factory=dict)

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        # Implement condition checks if necessary
        return True
