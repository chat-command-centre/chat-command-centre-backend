from __future__ import annotations
from asyncio import Queue
from datetime import datetime, timedelta
import logging
import multiprocessing
import os
from textwrap import dedent
import threading
from typing import (
    AsyncGenerator,
    Callable,
    ClassVar,
    Dict,
    List,
    Literal,
    Optional,
    Any,
)

from jinja2 import Template
from pydantic import BaseModel, Field

from sqlmodel import Relationship, SQLModel, Field as SQLField, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from loguru import logger  # Import Loguru
from croniter import croniter
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

import flask
from flask import Flask, request, jsonify
import imaplib
import email
import time

# Database configuration
DATABASE_URL = "postgresql+asyncpg://user:password@localhost/dbname"

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=True, future=True)

# Create async session
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Base model for SQLModel
class SQLModelBase(SQLModel):
    id: Optional[int] = SQLField(default=None, primary_key=True)


# Example of how to use SQLModel with your existing models
class EntityBase(SQLModelBase, table=True):
    __tablename__ = "entities"
    __type__: ClassVar[str] = Field(discriminator="type")

    name: str
    description: str

    def __init_subclass__(cls, **kwargs):
        cls.__type__ = cls.__name__
        return super().__init_subclass__(**kwargs)


# Function to initialize the database
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


# Dependency to get DB session
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


class DataSource(EntityBase):
    pass  # use raw sql for now


class Event(EntityBase):
    parent: Optional[Event] = None
    status: Literal["pending", "active", "success", "failure"] = "pending"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Service(EntityBase):
    state: Literal["running", "stopped"] = "stopped"

    def start(self):
        self.state = "running"

    def stop(self):
        self.state = "stopped"


class Context(EntityBase):
    system: "SystemBase"
    secrets: Dict[str, str] = Field(default_factory=dict)
    variables: Dict[str, str] = Field(default_factory=dict)


class TriggerDispatcherBase:
    def start(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def handle_event(self, event_data: Dict[str, Any]):
        raise NotImplementedError


class Trigger(ABC):
    dispatcher: TriggerDispatcherBase
    conditions: Dict[str, Any]

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        raise NotImplementedError


class TriggerEvent:
    pass


class CRONTriggerDispatcher(TriggerDispatcherBase):
    cron: str
    _stop_event: threading.Event = Field(default_factory=threading.Event)
    _logger: logging.Logger = Field(
        default_factory=lambda: logging.getLogger(f"{__name__}_{id(__name__)}")
    )
    _thread: Optional[threading.Thread] = None

    def start(self):
        self._logger.info(
            f"Starting CRON trigger dispatcher with schedule: {self.cron}"
        )
        self._thread = threading.Thread(target=self._cron_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._logger.info("Stopping CRON trigger dispatcher")
        self._stop_event.set()
        if self._thread:
            self._thread.join()

    def _cron_loop(self):
        cron = croniter(self.cron, datetime.now())
        while not self._stop_event.is_set():
            next_run = cron.get_next(datetime)
            wait_time = (next_run - datetime.now()).total_seconds()
            if wait_time > 0:
                if self._stop_event.wait(wait_time):
                    break
            event_data = {"timestamp": datetime.utcnow().isoformat()}
            self.handle_event(event_data)


class CRONTrigger(Trigger):
    dispatcher: CRONTriggerDispatcher
    conditions: Dict[str, Any] = Field(default_factory=dict)

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        # Implement condition checks if needed
        return True


class CRONTriggerFired(TriggerEvent, BaseModel):
    timestamp: str

    def __repr__(self) -> str:
        return f"CRONTriggerFired(timestamp={self.timestamp})"


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

    def handle_event(self, event_data: Dict[str, Any]):
        self._logger.info(f"Handling event data: {event_data}")
        # Here you can integrate with your event system, e.g., dispatch the event to listeners or triggers
        # For demonstration, we'll directly create and log the TriggerEvent
        trigger_event = WebhookTriggerFired(payload=event_data)
        self._logger.info(f"Dispatching event: {trigger_event}")


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
        self._logger.info(f"Starting email trigger dispatcher for: {self.email}")
        self._imap = imaplib.IMAP4_SSL(self.smtp_server, self.smtp_port)
        self._imap.login(self.username, self.password)
        self._thread = threading.Thread(target=self._email_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._logger.info("Stopping email trigger dispatcher")
        self._stop_event.set()
        if self._imap:
            try:
                self._imap.logout()
            except Exception as e:
                self._logger.error(f"Error logging out from IMAP: {e}")
        if self._thread:
            self._thread.join()

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
        self._logger.info(f"Handling email event data: {event_data}")
        # Here you can integrate with your event system, e.g., dispatch the event to listeners or triggers
        # For demonstration, we'll directly create and log the TriggerEvent
        trigger_event = EmailTriggerFired(**event_data)
        self._logger.info(f"Dispatching event: {trigger_event}")


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
    email: Email

    def __repr__(self) -> str:
        return f"EmailTriggerFired(email={self.email})"


class Contact(SQLModelBase, table=True):
    first_name: str
    last_name: str
    contact_methods: List[ContactMethod] = Relationship(back_populates="contact")


class ContactMethod(SQLModelBase, table=True):
    contact_id: int = Field(foreign_key="Contact.id")
    contact: Contact = Relationship(back_populates="contact_methods")
    value: str


class EmailAddress(ContactMethod):
    pass


class PhoneNumber(ContactMethod):
    pass


class Address(ContactMethod):
    pass


class Website(ContactMethod):
    pass


class SocialMediaHandle(ContactMethod):
    pass


class TwitterHandle(ContactMethod):
    pass


class InstagramHandle(ContactMethod):
    pass


class FacebookHandle(ContactMethod):
    pass


class LinkedInHandle(ContactMethod):
    pass


class TikTokHandle(ContactMethod):
    pass


class YouTubeHandle(ContactMethod):
    pass


class Email(SQLModelBase, table=True):
    subject: str
    body: str
    sender: EmailAddress
    cc_email_address_ids: List[int] = Field(default_factory=list)
    bcc_email_address_ids: List[int] = Field(default_factory=list)
    to_email_address_ids: List[int] = Field(default_factory=list)
    reply_to_email_address_id: Optional[int] = None
    in_reply_to: Optional[str] = None
    references: List[str] = Field(default_factory=list)
    subject: str
    body: str
    html_body: Optional[str] = None
    attachments: List[Attachment] = Field(default_factory=list)
    headers: Dict[str, str] = Field(default_factory=dict)
    date: datetime = Field(default_factory=datetime.utcnow)
    message_id: str
    mime_version: str
    content_type: str
    content_transfer_encoding: str


class Attachment(SQLModelBase, table=True):
    email_id: int = Field(foreign_key="Email.id")
    filename: str
    content_type: str
    content: bytes
    size: int
    disposition: Optional[str] = None
    content_id: Optional[str] = None
    content_location: Optional[str] = None


class LogEntry(SQLModelBase, table=True):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    message: str
    logger_id: int = Field(foreign_key="Logger.id")
    thread_name: str = Field(default_factory=lambda: threading.current_thread().name)
    thread_id: int = Field(default_factory=lambda: threading.get_ident())
    process_id: int = Field(default_factory=os.getpid)
    process_name: str = Field(
        default_factory=lambda: multiprocessing.current_process().name
    )


class Logger(DataSource):
    level: int = Field(default=logging.INFO)
    _handlers: List[str] = Field(default_factory=list)
    log_entries: List[LogEntry] = Relationship(back_populates="logger")
    template: str = dedent(
        """\
        Logger(name={{ self.name }}, level={{ self.level }}):
        {% for entry in self.log_entries %}
        {{ entry.timestamp }} [{{ entry.level }}]: {{ entry.message }}
        {% endfor %}
        """
    )
    storage_cutoff: Optional[int] = 1000
    display_cutoff: Optional[int] = 1000

    @classmethod
    def ddl(cls) -> str:
        return dedent(
            """\
            CREATE TRIGGER IF NOT EXISTS prune_log_entries
            AFTER INSERT ON {cls.__tablename__}
            BEGIN
                DELETE FROM {cls.__tablename__}
                WHERE id IN (
                    SELECT id 
                    FROM {cls.__tablename__}
                    WHERE logger_id = NEW.logger_id
                    ORDER BY timestamp ASC
                    LIMIT (
                        SELECT CASE
                            WHEN Logger.storage_cutoff IS NOT NULL THEN
                                MAX(0, COUNT(*) - Logger.storage_cutoff)
                            ELSE
                                0
                        END
                        FROM {cls.__tablename__} AS log
                        LEFT JOIN Logger ON Logger.id = log.logger_id
                        WHERE log.logger_id = NEW.logger_id
                    )
                )
                AND EXISTS (
                    SELECT 1
                    FROM Logger
                    WHERE Logger.id = NEW.logger_id
                    AND Logger.storage_cutoff IS NOT NULL
                );
            END;
            """
        )

    @property
    def _displayed_entries(self) -> List[LogEntry]:
        if self.display_cutoff is None:
            return self.log_entries
        if not self.log_entries:
            return []
        return self.log_entries[-min(self.display_cutoff, len(self.log_entries)) :]

    def log(
        self,
        level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        message: str,
    ):
        self.log_entries.append(
            LogEntry(level=level, message=message, logger_id=self.id)
        )

    @property
    def _jinja_template(self) -> str:
        return Template(self.template)

    def __str__(self):
        return self._jinja_template.render(self)

    def __repr__(self):
        return self._jinja_template.render(self)

    def write(self, message: str) -> None:
        """
        Loguru sink method to write log messages to the database.
        """
        # Parse the log message to extract level and message
        try:
            level, msg = message.split(":", 1)
            level = level.strip()
            msg = msg.strip()
        except ValueError:
            level = "INFO"
            msg = message.strip()

        # Ensure the level is one of the expected literals
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            level = "INFO"

        self.log(level, msg)

    def add_loguru_sink(self) -> None:
        """
        Add this Logger instance as a sink to Loguru.
        """
        logger.add(self.write, level="DEBUG")  # Adjust the level as needed


class PollingTriggerDispatcher(TriggerDispatcherBase):
    update_interval: int = 300  # 5 minutes by default
    _stop_event: threading.Event
    _logger: logging.Logger

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event = threading.Event()
        self._logger = logging.getLogger(f"{self.__class__.__name__}_{id(self)}")

    def start(self):
        super().start()
        self._logger.info("Starting polling trigger dispatcher")
        threading.Thread(target=self._polling_loop, daemon=True).start()

    def stop(self):
        super().stop()
        self._logger.info("Stopping polling trigger dispatcher")
        self._stop_event.set()

    def _polling_loop(self):
        while not self._stop_event.is_set():
            try:
                self._poll_and_handle_events()
            except Exception as e:
                self._logger.error(f"Error in polling loop: {str(e)}")
            self._stop_event.wait(self.update_interval)

    def _poll_and_handle_events(self):
        raise NotImplementedError("Subclasses must implement this method")


class Trigger(EntityBase):
    dispatcher: ClassVar[TriggerDispatcherBase]


class TriggerEvent(Event):
    trigger: Trigger


class TriggerFired(TriggerEvent):
    pass


class TriggerRegistered(TriggerEvent):
    pass


class TriggerUnregistered(TriggerEvent):
    pass


class EventSystem:
    listeners: Dict[str, List[Callable[[Event], None]]] = Field(default_factory=dict)

    def listen(self, channel: str, callback: Callable[[Event], None]):
        if channel not in self.listeners:
            self.listeners[channel] = []
        self.listeners[channel].append(callback)

    def dispatch(self, event: Event):
        channel = event.__class__.__name__
        if channel in self.listeners:
            for callback in self.listeners[channel]:
                callback(event)


class ServiceManager(Service):
    services: List[Service] = Field(default_factory=list)

    def start(self):
        for service in self.services:
            service.start()

    def stop(self):
        for service in self.services:
            service.stop()


class SystemBase(EventSystem, ServiceManager, EntityBase):
    triggers: List[Trigger] = Field(default_factory=list)


class Task(EntityBase):
    pass


class System(SystemBase):
    tasks: List[Task] = Field(default_factory=list)


# Calendar Event Trigger Dispatcher and Trigger

import threading
import time
from typing import Dict, Any, List, Literal
from pydantic import Field


# Assuming TriggerEvent and Trigger are defined elsewhere
class TriggerEvent:
    pass


class Trigger:
    pass


class PollingTriggerDispatcher:
    update_interval: int = 60  # default update interval in seconds
    _running: bool = False

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop)
        self._thread.start()

    def stop(self):
        self._running = False
        self._thread.join()

    def _poll_loop(self):
        while self._running:
            self._poll_and_handle_events()
            time.sleep(self.update_interval)

    def _poll_and_handle_events(self):
        raise NotImplementedError("Subclasses should implement this method")

    def dispatch(self, event):
        # Implement event dispatching logic here
        pass


import croniter
import datetime
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

import datetime
import threading
from typing import Dict, Any, List, Optional
from pydantic import Field
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import msal  # Microsoft Authentication Library
import requests  # For Outlook API calls

from icalendar import Calendar  # For Apple Calendar (.ics) parsing


class CalendarEventTriggerFired(TriggerEvent):
    event_data: Dict[str, Any]


class CalendarEventTriggerDispatcher(PollingTriggerDispatcher):
    update_interval: int = 60  # Seconds between calendar checks

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.calendar_client = self._initialize_calendar_client()

    def _initialize_calendar_client(self):
        # Default implementation returns None
        return None

    def _poll_and_handle_events(self):
        new_events = self.calendar_client.get_new_events()
        for event in new_events:
            self.handle_event(event)

    def handle_event(self, event_data: Dict[str, Any]):
        trigger_event = CalendarEventTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)

    def stop(self):
        super().stop()
        if hasattr(self.calendar_client, "close"):
            self.calendar_client.close()


# Implementations for Google Calendar, Outlook Calendar, and Apple Calendar


class GoogleCalendarClient:
    SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
    creds: Optional[Credentials] = None

    def __init__(self, credentials_file: str, token_file: str):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self._authenticate()

    def _authenticate(self):
        """Authenticate the Google Calendar API client."""
        if Path(self.token_file).exists():
            self.creds = Credentials.from_authorized_user_file(
                self.token_file, self.SCOPES
            )
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.SCOPES
                )
                self.creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(self.token_file, "w") as token:
                token.write(self.creds.to_json())
        self.service = build("calendar", "v3", credentials=self.creds)

    def get_new_events(self) -> List[Dict[str, Any]]:
        """Fetch new events from the user's primary calendar."""
        now = datetime.datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
        events_result = (
            self.service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        return events

    def close(self):
        pass  # No explicit close action required for Google Calendar API


class GoogleCalendarEventTriggerDispatcher(CalendarEventTriggerDispatcher):
    credentials_file: str
    token_file: str

    def _initialize_calendar_client(self):
        return GoogleCalendarClient(self.credentials_file, self.token_file)


class OutlookCalendarClient:
    def __init__(self, client_id: str, client_secret: str, tenant_id: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self._authenticate()

    def _authenticate(self):
        """Authenticate the Outlook Calendar API client."""
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.app = msal.ConfidentialClientApplication(
            self.client_id, authority=authority, client_credential=self.client_secret
        )
        scopes = ["https://graph.microsoft.com/.default"]
        result = self.app.acquire_token_silent(scopes, account=None)
        if not result:
            result = self.app.acquire_token_for_client(scopes=scopes)
        if "access_token" in result:
            self.access_token = result["access_token"]
            self.headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
        else:
            raise Exception("Could not obtain access token")

    def get_new_events(self) -> List[Dict[str, Any]]:
        """Fetch new events from the user's primary calendar."""
        endpoint = "https://graph.microsoft.com/v1.0/me/events"
        params = {
            "$select": "subject,organizer,start,end",
            "$orderby": "start/dateTime ASC",
        }
        response = requests.get(endpoint, headers=self.headers, params=params)
        response.raise_for_status()
        events = response.json().get("value", [])
        return events

    def close(self):
        pass  # No explicit close action required for Outlook Calendar API


class OutlookCalendarEventTriggerDispatcher(CalendarEventTriggerDispatcher):
    client_id: str
    client_secret: str
    tenant_id: str

    def _initialize_calendar_client(self):
        return OutlookCalendarClient(self.client_id, self.client_secret, self.tenant_id)


class AppleCalendarClient:
    def __init__(self, calendar_file_path: str):
        self.calendar_file_path = calendar_file_path

    def get_new_events(self) -> List[Dict[str, Any]]:
        """Fetch new events from a local Apple Calendar (.ics) file."""
        with open(self.calendar_file_path, "rb") as f:
            gcal = Calendar.from_ical(f.read())

        events = []
        for component in gcal.walk():
            if component.name == "VEVENT":
                event = {
                    "summary": component.get("summary"),
                    "dtstart": component.get("dtstart").dt,
                    "dtend": component.get("dtend").dt,
                    "description": component.get("description"),
                    "location": component.get("location"),
                }
                events.append(event)
        return events

    def close(self):
        pass  # No explicit close action required for Apple Calendar


class AppleCalendarEventTriggerDispatcher(CalendarEventTriggerDispatcher):
    calendar_file_path: str

    def _initialize_calendar_client(self):
        return AppleCalendarClient(self.calendar_file_path)


class CalendarEventTrigger(Trigger):
    dispatcher: CalendarEventTriggerDispatcher
    event_type: Literal["meeting", "reminder", "all_day", "recurring"]
    conditions: Dict[str, Any] = Field(default_factory=dict)

    def __init__(
        self,
        dispatcher: CalendarEventTriggerDispatcher,
        event_type: Literal["meeting", "reminder", "all_day", "recurring"],
        conditions: Dict[str, Any] = None,
    ):
        super().__init__()
        self.dispatcher = dispatcher
        self.event_type = event_type
        self.conditions = conditions or {}
        self.dispatcher.start()

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        # Implement logic to check if event_data meets the conditions
        # Example: Check if event type matches and conditions are met
        if self.event_type == "all_day":
            is_all_day = "date" in event_data.get("start", {})
            if not is_all_day:
                return False
        # Additional condition checks can be implemented here
        for key, value in self.conditions.items():
            if event_data.get(key) != value:
                return False
        return True


import fnmatch
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
import threading
import time


# File System Change Trigger Dispatcher and Trigger
class FileSystemTriggerDispatcher(TriggerDispatcherBase):
    path: str
    event_types: List[Literal["created", "modified", "deleted"]]
    _observer: Optional[Observer] = None  # type: ignore
    _event_handler: Optional[FileSystemEventHandler] = None

    def start(self):
        super().start()
        self._event_handler = self._create_event_handler()
        self._observer = Observer()
        self._observer.schedule(self._event_handler, self.path, recursive=True)
        self._observer.start()
        logging.info(f"Started FileSystemTriggerDispatcher monitoring {self.path}")

    def stop(self):
        super().stop()
        if self._observer:
            self._observer.stop()
            self._observer.join()
            logging.info(f"Stopped FileSystemTriggerDispatcher monitoring {self.path}")

    def _create_event_handler(self) -> FileSystemEventHandler:
        dispatcher = self

        class Handler(FileSystemEventHandler):
            def on_any_event(self, event: FileSystemEvent):
                if event.is_directory:
                    return  # Skip directories
                event_type = (
                    event.event_type
                )  # 'created', 'modified', 'deleted', 'moved'
                if event_type not in dispatcher.event_types:
                    return
                # Check if the file matches any of the patterns
                for pattern in dispatcher.file_patterns:
                    if fnmatch.fnmatch(event.src_path, pattern):
                        event_data = {
                            "event_type": event_type,
                            "src_path": event.src_path,
                            "is_directory": event.is_directory,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                        dispatcher.handle_event(event_data)
                        break  # Avoid duplicate triggers for multiple patterns

        return Handler()


class FileSystemChangeTrigger(Trigger):
    dispatcher: FileSystemTriggerDispatcher
    file_patterns: List[str]  # e.g., '*.txt', '*.log'
    conditions: Dict[str, Any]

    def __init__(
        self,
        dispatcher: FileSystemTriggerDispatcher,
        file_patterns: List[str],
        conditions: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        self.dispatcher = dispatcher
        self.file_patterns = file_patterns
        self.conditions = conditions or {}
        self.dispatcher.file_patterns = self.file_patterns
        self.dispatcher.conditions = self.conditions
        self.dispatcher.start()

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        # Implement additional condition checks if necessary
        # For example, filter based on file size, user, etc.
        for key, value in self.conditions.items():
            if event_data.get(key) != value:
                return False
        return True


class FileSystemChangeTriggerFired(TriggerEvent):
    event_data: dict

    def __init__(self, event_data: dict):
        super().__init__()
        self.event_data = event_data

    def __repr__(self):
        return f"FileSystemChangeTriggerFired(event_data={self.event_data})"


# Stock Market Trigger Dispatcher and Trigger
class StockMarketTriggerDispatcher(TriggerDispatcherBase):
    stock_symbols: List[str]
    update_interval: int  # Seconds between updates

    def start(self):
        super().start()
        # Implement stock market monitoring logic here

    def stop(self):
        super().stop()
        # Implement logic to stop monitoring stock market

    def handle_event(self, event_data: dict):
        trigger_event = StockMarketTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class StockMarketTrigger(Trigger):
    dispatcher: StockMarketTriggerDispatcher
    conditions: List[StockCondition]


class StockCondition(BaseModel):
    stock_symbol: str
    comparison: Literal["above", "below", "equal"]


class PriceCondition(StockCondition):
    value: float


class PercentageChangeCondition(StockCondition):
    value: float
    time_frame: str  # e.g., "1-day", "5-day", "30-day"


class VolumeCondition(StockCondition):
    value: int


class MovingAverageCondition(StockCondition):
    value: float
    time_frame: str  # e.g., "5-day", "20-day", "50-day", "200-day"


class RelativeStrengthIndexCondition(StockCondition):
    value: float
    time_frame: str  # e.g., "14-day", "28-day"


class BollingerBandsCondition(StockCondition):
    band: Literal["upper", "lower", "middle"]
    value: float
    time_frame: str  # e.g., "20-day"
    standard_deviations: float  # typically 2


class MACDCondition(StockCondition):
    signal_line: float
    macd_line: float
    fast_period: int  # typically 12
    slow_period: int  # typically 26
    signal_period: int  # typically 9


class StochasticOscillatorCondition(StockCondition):
    value: float
    k_period: int  # typically 14
    d_period: int  # typically 3


class EarningsPerShareCondition(StockCondition):
    value: float


class PriceToEarningsRatioCondition(StockCondition):
    value: float


class DividendYieldCondition(StockCondition):
    value: float


class StockMarketTriggerFired(TriggerEvent):
    event_data: dict
    triggered_conditions: List[StockCondition]


# Update WeatherAlertTriggerDispatcher to inherit from PollingTriggerDispatcher
class WeatherAlertTriggerDispatcher(PollingTriggerDispatcher):
    location: str
    alert_types: List[str]
    api_key: str

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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


class WeatherAlertTriggerFired(TriggerEvent):
    event_data: dict


class WeatherService:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_alerts(self, location: str, alert_types: List[str]) -> List[dict]:
        # Implement API call to weather service
        # This is a placeholder implementation
        return [
            {
                "type": "storm",
                "severity": "high",
                "description": "Severe thunderstorm warning",
                "start_time": datetime.now().isoformat(),
                "end_time": (datetime.now() + timedelta(hours=2)).isoformat(),
            }
        ]


# Social Media Trigger Dispatcher and Trigger
class SocialMediaTriggerDispatcher(TriggerDispatcherBase):
    platform: str  # e.g., 'Twitter', 'Facebook'
    credentials: Dict[str, str]
    keywords: List[str]

    def start(self):
        super().start()
        # Implement social media monitoring logic here

    def stop(self):
        super().stop()
        # Implement logic to stop monitoring social media

    def handle_event(self, event_data: dict):
        trigger_event = SocialMediaTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class SocialMediaMentionTrigger(Trigger):
    dispatcher: SocialMediaTriggerDispatcher
    keyword: str
    user_handle: Optional[str]


class SocialMediaTriggerFired(TriggerEvent):
    event_data: dict


# Geolocation Trigger Dispatcher and Trigger
class GeoLocationTriggerDispatcher(TriggerDispatcherBase):
    device_id: str  # ID of the device to monitor

    def start(self):
        super().start()
        # Implement geolocation monitoring logic here

    def stop(self):
        super().stop()
        # Implement logic to stop monitoring geolocation

    def handle_event(self, event_data: dict):
        trigger_event = GeoLocationTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class GeoFenceTrigger(Trigger):
    dispatcher: GeoLocationTriggerDispatcher
    area: Dict[str, Any]  # Define the geofence area
    enter_exit: Literal["enter", "exit"]


class GeoLocationTriggerFired(TriggerEvent):
    event_data: dict


# Sensor Data Trigger Dispatcher and Trigger
class SensorDataTriggerDispatcher(TriggerDispatcherBase):
    sensor_id: str  # ID of the sensor to monitor

    def start(self):
        super().start()
        # Implement sensor data monitoring logic here

    def stop(self):
        super().stop()
        # Implement logic to stop monitoring sensor data

    def handle_event(self, event_data: dict):
        trigger_event = SensorDataTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class SensorThresholdTrigger(Trigger):
    dispatcher: SensorDataTriggerDispatcher
    threshold_value: float
    condition: Literal["above", "below"]


class SensorDataTriggerFired(TriggerEvent):
    event_data: dict


# Messaging App Trigger Dispatcher and Trigger
class MessagingAppTriggerDispatcher(TriggerDispatcherBase):
    platform: str  # e.g., 'Slack', 'Teams'
    credentials: Dict[str, str]
    channels: List[str]

    def start(self):
        super().start()
        # Implement messaging app monitoring logic here

    def stop(self):
        super().stop()
        # Implement logic to stop monitoring messaging app

    def handle_event(self, event_data: dict):
        trigger_event = MessagingAppTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class MessagingAppMessageTrigger(Trigger):
    dispatcher: MessagingAppTriggerDispatcher
    keyword: Optional[str]
    user: Optional[str]


class MessagingAppTriggerFired(TriggerEvent):
    event_data: dict


# System Resource Trigger Dispatcher and Trigger
class SystemResourceTriggerDispatcher(TriggerDispatcherBase):
    resource_type: Literal["cpu", "memory", "disk"]
    threshold: float  # Percentage

    def start(self):
        super().start()
        # Implement system resource monitoring logic here

    def stop(self):
        super().stop()
        # Implement logic to stop monitoring system resources

    def handle_event(self, event_data: dict):
        trigger_event = SystemResourceTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class SystemResourceThresholdTrigger(Trigger):
    dispatcher: SystemResourceTriggerDispatcher
    condition: Literal["above", "below"]
    threshold_value: float


class SystemResourceTriggerFired(TriggerEvent):
    event_data: dict


# Payment Transaction Trigger Dispatcher and Trigger
class PaymentTransactionTriggerDispatcher(TriggerDispatcherBase):
    payment_provider: str  # e.g., 'Stripe', 'PayPal'
    credentials: Dict[str, str]

    def start(self):
        super().start()
        # Implement payment transaction monitoring logic here

    def stop(self):
        super().stop()
        # Implement logic to stop monitoring payment transactions

    def handle_event(self, event_data: dict):
        trigger_event = PaymentTransactionTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class PaymentTransactionTrigger(Trigger):
    dispatcher: PaymentTransactionTriggerDispatcher
    transaction_type: Literal["payment", "refund"]
    amount_condition: Dict[str, Any]  # e.g., {'greater_than': 100}


class PaymentTransactionTriggerFired(TriggerEvent):
    event_data: dict


# User Signup Trigger Dispatcher and Trigger
class UserSignupTriggerDispatcher(TriggerDispatcherBase):
    platform: str  # e.g., 'Website', 'MobileApp'

    def start(self):
        super().start()
        # Implement user signup monitoring logic here

    def stop(self):
        super().stop()
        # Implement logic to stop monitoring user signups

    def handle_event(self, event_data: dict):
        trigger_event = UserSignupTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class UserSignupTrigger(Trigger):
    dispatcher: UserSignupTriggerDispatcher
    conditions: Dict[str, Any]  # Conditions on user data


class UserSignupTriggerFired(TriggerEvent):
    event_data: dict


# Error Log Trigger Dispatcher and Trigger
class ErrorLogTriggerDispatcher(TriggerDispatcherBase):
    log_file_path: str
    error_level: Literal["ERROR", "WARNING", "CRITICAL"]

    def start(self):
        super().start()
        # Implement error log monitoring logic here

    def stop(self):
        super().stop()
        # Implement logic to stop monitoring error logs

    def handle_event(self, event_data: dict):
        trigger_event = ErrorLogTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class ErrorLogTrigger(Trigger):
    dispatcher: ErrorLogTriggerDispatcher
    error_message_contains: Optional[str]


class ErrorLogTriggerFired(TriggerEvent):
    event_data: dict


# Build Pipeline Trigger Dispatcher and Trigger
class BuildPipelineTriggerDispatcher(TriggerDispatcherBase):
    ci_cd_tool: str  # e.g., 'Jenkins', 'GitHub Actions'
    credentials: Dict[str, str]

    def start(self):
        super().start()
        # Implement build pipeline monitoring logic here

    def stop(self):
        super().stop()
        # Implement logic to stop monitoring build pipelines

    def handle_event(self, event_data: dict):
        trigger_event = BuildPipelineTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class BuildPipelineTrigger(Trigger):
    dispatcher: BuildPipelineTriggerDispatcher
    pipeline_name: str
    build_status: Literal["success", "failure"]


class BuildPipelineTriggerFired(TriggerEvent):
    event_data: dict


# Database Event Trigger Dispatcher and Trigger
class DatabaseEventTriggerDispatcher(TriggerDispatcherBase):
    database_url: str
    tables: List[str]

    def start(self):
        super().start()
        # Implement database event monitoring logic here

    def stop(self):
        super().stop()
        # Implement logic to stop monitoring database events

    def handle_event(self, event_data: dict):
        trigger_event = DatabaseEventTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class DatabaseEventTrigger(Trigger):
    dispatcher: DatabaseEventTriggerDispatcher
    table_name: str
    operation: Literal["insert", "update", "delete"]


class DatabaseEventTriggerFired(TriggerEvent):
    event_data: dict


# Network Event Trigger Dispatcher and Trigger
class NetworkEventTriggerDispatcher(TriggerDispatcherBase):
    ip_addresses: List[str]
    ports: List[int]

    def start(self):
        super().start()
        # Implement network event monitoring logic here

    def stop(self):
        super().stop()
        # Implement logic to stop monitoring network events

    def handle_event(self, event_data: dict):
        trigger_event = NetworkEventTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class NetworkEventTrigger(Trigger):
    dispatcher: NetworkEventTriggerDispatcher
    protocol: Literal["TCP", "UDP"]
    conditions: Dict[str, Any]


class NetworkEventTriggerFired(TriggerEvent):
    event_data: dict


# System Startup/Shutdown Trigger Dispatcher and Trigger
class SystemEventTriggerDispatcher(TriggerDispatcherBase):
    event_types: List[Literal["startup", "shutdown"]]

    def start(self):
        super().start()
        # Implement system event monitoring logic here

    def stop(self):
        super().stop()
        # Implement logic to stop monitoring system events

    def handle_event(self, event_data: dict):
        trigger_event = SystemEventTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class SystemEventTrigger(Trigger):
    dispatcher: SystemEventTriggerDispatcher
    event_type: Literal["startup", "shutdown"]


class SystemEventTriggerFired(TriggerEvent):
    event_data: dict


# Time-Based Trigger Dispatcher and Trigger
class TimeTriggerDispatcher(TriggerDispatcherBase):
    schedule: str  # e.g., cron expression

    def start(self):
        super().start()
        # Implement time-based trigger logic here

    def stop(self):
        super().stop()
        # Implement logic to stop time-based triggers

    def handle_event(self, event_data: dict):
        trigger_event = TimeTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class TimeTrigger(Trigger):
    dispatcher: TimeTriggerDispatcher
    time_conditions: Dict[str, Any]  # e.g., {'hour': 14, 'minute': 30}


class TimeTriggerFired(TriggerEvent):
    event_data: dict


# Voice Command Trigger Dispatcher and Trigger
class VoiceCommandTriggerDispatcher(TriggerDispatcherBase):
    keywords: List[str]

    def start(self):
        super().start()
        # Implement voice command detection logic here

    def stop(self):
        super().stop()
        # Implement logic to stop voice command detection

    def handle_event(self, event_data: dict):
        trigger_event = VoiceCommandTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class VoiceCommandTrigger(Trigger):
    dispatcher: VoiceCommandTriggerDispatcher
    command: str


class VoiceCommandTriggerFired(TriggerEvent):
    event_data: dict


# Email Received Trigger Dispatcher and Trigger
class EmailReceivedTriggerDispatcher(TriggerDispatcherBase):
    email_address: str
    credentials: Dict[str, str]

    def start(self):
        super().start()
        # Implement email receiving logic here

    def stop(self):
        super().stop()
        # Implement logic to stop email monitoring

    def handle_event(self, event_data: dict):
        trigger_event = EmailReceivedTriggerFired(event_data=event_data)
        self.dispatch(trigger_event)


class EmailReceivedTrigger(Trigger):
    dispatcher: EmailReceivedTriggerDispatcher
    sender_email: Optional[str]
    subject_contains: Optional[str]


class EmailReceivedTriggerFired(TriggerEvent):
    event_data: dict
