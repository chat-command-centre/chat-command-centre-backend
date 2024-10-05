from azure.identity.aio import DefaultAzureCredential
from azure.eventhub.aio import EventHubConsumerClient
from .dispatcher_base import CloudProviderDispatcherBase
import asyncio


class AzureDispatcher(CloudProviderDispatcherBase):
    def __init__(self, fully_qualified_namespace, eventhub_name):
        self.fully_qualified_namespace = fully_qualified_namespace
        self.eventhub_name = eventhub_name
        self.credential = DefaultAzureCredential()
        self.client = EventHubConsumerClient.from_connection_string(
            conn_str=f"Endpoint=sb://{self.fully_qualified_namespace}/;",
            consumer_group="$Default",
            eventhub_name=self.eventhub_name,
            credential=self.credential,
        )
        self.event_manager = None

    async def authenticate(self):
        # Authentication is handled via DefaultAzureCredential
        pass

    async def on_event(self, partition_context, event):
        event_data = {
            # Extract relevant data from the event
        }
        self.dispatch_event(event_data)
        await partition_context.update_checkpoint(event)

    def dispatch_event(self, event_data):
        if self.event_manager:
            self.event_manager.dispatch(event_data)

    async def start(self):
        await self.client.receive(
            on_event=self.on_event,
            starting_position="-1",  # "-1" is from the beginning of the partition.
        )

    async def stop(self):
        await self.client.close()
        await self.credential.close()
