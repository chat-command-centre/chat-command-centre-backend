from typing import Dict, Any, List
from pydantic import BaseModel, Field
from command_centre_python.utils.triggers import (
    TriggerDispatcherBase,
    Trigger,
    TriggerEvent,
)
import threading
import speech_recognition as sr  # For voice recognition
import logging

logger = logging.getLogger(__name__)


class VoiceCommandTriggerFired(TriggerEvent):
    event_data: dict


class VoiceCommandTriggerDispatcher(TriggerDispatcherBase):
    keywords: List[str]
    _stop_event: threading.Event = threading.Event()

    def start(self):
        threading.Thread(target=self._listen_for_commands, daemon=True).start()
        logger.info("VoiceCommandTriggerDispatcher started")

    def _listen_for_commands(self):
        recognizer = sr.Recognizer()
        microphone = sr.Microphone()
        while not self._stop_event.is_set():
            with microphone as source:
                recognizer.adjust_for_ambient_noise(source)
                try:
                    logger.info("Listening for voice commands...")
                    audio = recognizer.listen(source, timeout=5)
                    command = recognizer.recognize_google(audio)
                    self.handle_event({"command": command})
                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    logger.warning("Could not understand audio")
                except Exception as e:
                    logger.error(f"Error in voice recognition: {e}")

    def stop(self):
        self._stop_event.set()
        logger.info("VoiceCommandTriggerDispatcher stopped")

    def handle_event(self, event_data: dict):
        trigger_event = VoiceCommandTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class VoiceCommandTrigger(Trigger):
    dispatcher: VoiceCommandTriggerDispatcher
    command: str

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        recognized_command = event_data.get("command", "").lower()
        return self.command.lower() in recognized_command
