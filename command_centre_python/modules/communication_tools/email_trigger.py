from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from command_centre_python.utils.triggers import (
    TriggerDispatcherBase,
    Trigger,
    TriggerEvent,
)
import threading
import imaplib
import email
import time
import logging

logger = logging.getLogger(__name__)


class EmailTriggerFired(TriggerEvent):
    subject: str
    body: str
    sender: str


class EmailTriggerDispatcher(TriggerDispatcherBase):
    email: str
    smtp_server: str
    smtp_port: int
    username: str
    password: str
    _stop_event: threading.Event = Field(default_factory=threading.Event)
    _logger: logging.Logger = Field(
        default_factory=lambda: logging.getLogger(f"{__name__}_{id(__name__)}")
    )
    _thread: Optional[threading.Thread] = None
    _imap: Optional[imaplib.IMAP4_SSL] = None

    def start(self):
        self._stop_event = threading.Event()
        self._imap = imaplib.IMAP4_SSL(self.smtp_server, self.smtp_port)
        self._imap.login(self.username, self.password)
        self._thread = threading.Thread(target=self._email_loop, daemon=True)
        self._thread.start()
        logger.info("EmailTriggerDispatcher started")

    def stop(self):
        self._stop_event.set()
        if self._imap:
            try:
                self._imap.logout()
            except Exception as e:
                self._logger.error(f"Error logging out from IMAP: {e}")
        if self._thread:
            self._thread.join()
        logger.info("EmailTriggerDispatcher stopped")

    def _email_loop(self):
        while not self._stop_event.is_set():
            try:
                self._imap.select("INBOX")
                result, data = self._imap.search(None, "UNSEEN")
                if result == "OK":
                    for num in data[0].split():
                        result, msg_data = self._imap.fetch(num, "(RFC822)")
                        if result == "OK":
                            msg = email.message_from_bytes(msg_data[0][1])
                            subject = self._decode_mime_words(msg["Subject"])
                            from_ = msg.get("From")
                            body = self._get_email_body(msg)
                            self._logger.info(
                                f"Received email from {from_} with subject '{subject}'"
                            )
                            event_data = {
                                "subject": subject,
                                "body": body,
                                "sender": from_,
                            }
                            self.handle_event(event_data)
                            self._imap.store(num, "+FLAGS", "\\Seen")
                time.sleep(10)  # Poll every 10 seconds
            except Exception as e:
                self._logger.error(f"Error in email loop: {e}")
                time.sleep(10)

    def _decode_mime_words(self, s):
        decoded_words = email.header.decode_header(s)
        return "".join(
            [
                word.decode(encoding or "utf-8") if isinstance(word, bytes) else word
                for word, encoding in decoded_words
            ]
        )

    def _get_email_body(self, msg):
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if (
                    content_type == "text/plain"
                    and "attachment" not in content_disposition
                ):
                    return part.get_payload(decode=True).decode()
        else:
            return msg.get_payload(decode=True).decode()
        return ""

    def handle_event(self, event_data: Dict[str, Any]):
        trigger_event = EmailTriggerFired(**event_data)
        self.dispatch(trigger_event)


class EmailTrigger(Trigger):
    dispatcher: EmailTriggerDispatcher
    conditions: Dict[str, Any] = Field(default_factory=dict)

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        # Example condition: subject starts with a specific prefix
        subject_prefix = self.conditions.get("subject_prefix")
        if subject_prefix and not event_data["subject"].startswith(subject_prefix):
            return False

        # Add more condition checks as needed
        for key, value in self.conditions.items():
            if key != "subject_prefix" and event_data.get(key) != value:
                return False
        return True


class EmailTriggerFired(TriggerEvent, BaseModel):
    subject: str
    body: str
    sender: str

    def __repr__(self) -> str:
        return f"EmailTriggerFired(subject='{self.subject}', sender='{self.sender}')"
