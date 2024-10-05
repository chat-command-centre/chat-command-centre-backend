import boto3
from .dispatcher_base import CloudProviderDispatcherBase
from typing import Dict, Any
import asyncio


class AWSDispatcher(CloudProviderDispatcherBase):
    def __init__(self, aws_access_key_id, aws_secret_access_key, region_name):
        self.session = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )
        self.event_manager = None
        self._running = False

    def authenticate(self):
        # Authentication is handled via boto3 session
        pass

    async def monitor_events(self):
        self._running = True
        while self._running:
            # Poll for AWS events (e.g., CloudWatch events)
            await asyncio.sleep(5)  # Adjust polling interval as needed
            # Fetch events and dispatch
            events = self.fetch_events()
            for event in events:
                self.dispatch_event(event)

    def fetch_events(self) -> list:
        # Implement logic to fetch events from AWS services
        return []

    def dispatch_event(self, event: Dict[str, Any]):
        if self.event_manager:
            self.event_manager.dispatch(event)

    def start(self):
        asyncio.create_task(self.monitor_events())

    def stop(self):
        self._running = False
