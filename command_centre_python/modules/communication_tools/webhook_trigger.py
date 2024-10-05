from typing import Dict, Any
from pydantic import BaseModel, Field
from command_centre_python.utils.triggers import (
    TriggerDispatcherBase,
    Trigger,
    TriggerEvent,
)
from flask import Flask, request, jsonify
import threading


class WebhookTriggerDispatcher(TriggerDispatcherBase):
    url: str
    _stop_event: threading.Event = Field(default_factory=threading.Event)
    _logger: logging.Logger = Field(
        default_factory=lambda: logging.getLogger(f"{__name__}_{id(__name__)}")
    )
    _app: Optional[Flask] = None
    _thread: Optional[threading.Thread] = None

    def start(self):
        self._logger.info(f"Starting webhook trigger dispatcher for URL: {self.url}")
        self._app = Flask(__name__)
        self._app.add_url_rule("/", "webhook", self._handle_webhook, methods=["POST"])
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()

    def stop(self):
        self._logger.info("Stopping webhook trigger dispatcher")
        self._stop_event.set()
        if self._app:
            func = request.environ.get("werkzeug.server.shutdown")
            if func:
                func()
        if self._thread:
            self._thread.join()

    def _run_server(self):
        self._app.run(host="0.0.0.0", port=5000)

    def _handle_webhook(self):
        if self._stop_event.is_set():
            return jsonify({"status": "dispatcher stopped"}), 503
        payload = request.get_json()
        self._logger.info(f"Received webhook payload: {payload}")
        self.handle_event(payload)
        return jsonify({"status": "received"}), 200


class WebhookTrigger(Trigger):
    dispatcher: WebhookTriggerDispatcher
    conditions: Dict[str, Any] = Field(default_factory=dict)

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        return all(
            event_data.get(key) == value for key, value in self.conditions.items()
        )


class WebhookTriggerFired(TriggerEvent, BaseModel):
    payload: Dict[str, Any]

    def __repr__(self) -> str:
        return f"WebhookTriggerFired(payload={self.payload})"
