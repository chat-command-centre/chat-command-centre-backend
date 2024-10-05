from ...utils.triggers import Trigger, TriggerEvent
from .aws_dispatcher import AWSDispatcher
from typing import Dict, Any


class AWSS3Event(TriggerEvent):
    bucket_name: str
    object_key: str
    event_type: str  # e.g., 'ObjectCreated', 'ObjectRemoved'


class AWSS3Trigger(Trigger):
    dispatcher: AWSDispatcher
    bucket_name: str
    event_type: str

    def __init__(self, dispatcher: AWSDispatcher, bucket_name: str, event_type: str):
        self.dispatcher = dispatcher
        self.bucket_name = bucket_name
        self.event_type = event_type

    def check_conditions(self, event_data: Dict[str, Any]) -> bool:
        return (
            event_data.get("bucket_name") == self.bucket_name
            and event_data.get("event_type") == self.event_type
        )

    async def handle_event(self, event_data: Dict[str, Any]):
        if self.check_conditions(event_data):
            # Define the action to take when the event occurs
            print(f"S3 event detected: {event_data}")
            # You can invoke actions or further processing here
